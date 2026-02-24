import isodate
import requests
from typing import List, Dict, Tuple
from flask import current_app
from sqlalchemy import func

from common.extensions import db
from common.enum.youtube_genre import GenreEnum
from common.utils.logging_utils import get_logger

logger = get_logger('youtube_category_fill_job')


CATEGORY_SEARCH_QUERIES: Dict[GenreEnum, List[str]] = {
    GenreEnum.EATING:      ['먹방 한국', '맛집 리뷰', 'mukbang asmr'],
    GenreEnum.DRAMA:       ['한국드라마 명장면', 'kdrama 클립', '드라마 하이라이트'],
    GenreEnum.COOK:        ['요리 레시피 한국', '집밥 만들기', '간단 요리 초보'],
    GenreEnum.HORROR:      ['공포 영상 한국', '귀신 영상', '호러 콘텐츠'],
    GenreEnum.EXERCISE:    ['홈트 운동 루틴', '다이어트 운동', '헬스 운동 초보'],
    GenreEnum.VLOG:        ['일상 브이로그 한국', '데일리 vlog', '주간 vlog 한국'],
    GenreEnum.BEAUTY:      ['메이크업 튜토리얼 한국', '스킨케어 루틴', '뷰티 리뷰 한국'],
    GenreEnum.COMEDY:      ['웃긴 영상 한국', '개그 콘텐츠', '코미디 클립'],
    GenreEnum.ANIMAL:      ['강아지 고양이 귀여운', '동물 영상 한국', '펫 vlog'],
    GenreEnum.INFORMATION: ['지식 교육 영상 한국', '유익한 정보 한국', '교양 콘텐츠'],
    GenreEnum.SPORTS:      ['스포츠 하이라이트 한국', '축구 야구 농구 한국', '스포츠 영상'],
    GenreEnum.TRAVEL:      ['국내여행 브이로그', '해외여행 영상 한국', '여행 vlog'],
    GenreEnum.SHOW:        ['예능 하이라이트 한국', '버라이어티 클립', '웃긴 예능'],
    GenreEnum.MUSIC:       ['신곡 뮤직비디오 한국', 'kpop mv', '한국 음악 최신'],
    GenreEnum.GAME:        ['게임 플레이 한국', '게임 리뷰 한국', '인디게임 한국'],
    GenreEnum.ETC:         ['한국 유튜브 인기 영상', '화제 영상 한국'],
}

TARGET_MIN_COUNT = 20
MAX_SEARCH_CALLS = 12  #NOTE: search.list = 100 quota/call → 최대 1,200 quota/run
SEARCH_MAX_RESULTS = 20


class YoutubeCategoryFillJob:

    def __init__(self):
        self.api_key: str = None
        self.quota_used: int = 0

    def _check_category_counts(self) -> Dict[GenreEnum, int]:
        from app.models.video import Video

        rows = (
            db.session.query(Video.category, func.count(Video.video_id).label('cnt'))
            .filter(Video.is_deleted == 0)
            .group_by(Video.category)
            .all()
        )
        return {row.category: row.cnt for row in rows}

    def _priority_targets(self, counts: Dict[GenreEnum, int]) -> List[Tuple[GenreEnum, int]]:
        targets = [
            (genre, counts.get(genre, 0))
            for genre in CATEGORY_SEARCH_QUERIES
            if counts.get(genre, 0) < TARGET_MIN_COUNT
        ]

        if not targets:
            #NOTE: 모두 기준치 이상이어도 신규 영상 확보를 위해 최하위 5개 보충
            all_sorted = sorted(
                [(g, counts.get(g, 0)) for g in CATEGORY_SEARCH_QUERIES],
                key=lambda x: x[1]
            )
            targets = all_sorted[:5]
            logger.info("모든 카테고리가 기준치 이상. 최하위 5개 카테고리 보충 실행.")

        # 부족분 많은 순(영상 수 적은 순) 정렬
        targets.sort(key=lambda x: x[1])
        return targets

    def _search_video_ids(self, query: str) -> List[str]:
        try:
            resp = requests.get(
                'https://www.googleapis.com/youtube/v3/search',
                params={
                    'part': 'id',
                    'q': query,
                    'type': 'video',
                    'regionCode': 'KR',
                    'relevanceLanguage': 'ko',
                    'maxResults': SEARCH_MAX_RESULTS,
                    'order': 'viewCount',
                    'key': self.api_key,
                },
                timeout=10
            )
            resp.raise_for_status()
            self.quota_used += 100

            ids = [
                item['id']['videoId']
                for item in resp.json().get('items', [])
                if item.get('id', {}).get('kind') == 'youtube#video'
            ]
            logger.info(f"검색 '{query}': {len(ids)}개 ID 수집 (누적 quota: {self.quota_used})")
            return ids

        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 403:
                logger.error("YouTube API quota 초과(403). 이번 실행 중단.")
                #NOTE: quota_used를 한도 초과값으로 설정 → 이후 루프에서 자동 break
                self.quota_used = MAX_SEARCH_CALLS * 100 + 1
            else:
                logger.error(f"YouTube search API 오류 ({query}): {e}")
            return []
        except Exception as e:
            logger.error(f"YouTube search API 오류 ({query}): {e}")
            return []

    def _fetch_video_details(self, video_ids: List[str]) -> List[Dict]:
        if not video_ids:
            return []

        results = []
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i:i + 50]
            try:
                resp = requests.get(
                    'https://www.googleapis.com/youtube/v3/videos',
                    params={
                        'part': 'snippet,contentDetails,statistics',
                        'id': ','.join(batch),
                        'key': self.api_key,
                    },
                    timeout=10
                )
                resp.raise_for_status()
                self.quota_used += 1

                for item in resp.json().get('items', []):
                    snippet = item.get('snippet', {})
                    content = item.get('contentDetails', {})

                    try:
                        duration_sec = int(
                            isodate.parse_duration(content.get('duration', 'PT0S')).total_seconds()
                        )
                    except Exception:
                        duration_sec = 0

                    results.append({
                        'youtube_id': item['id'],
                        'title': snippet.get('title', ''),
                        'channel_name': snippet.get('channelTitle', ''),
                        'duration': duration_sec,
                    })

            except Exception as e:
                logger.error(f"videos.list API 오류 (batch {i}): {e}")

        return results

    def _save_videos(self, video_list: List[Dict], target_category: GenreEnum) -> int:
        from app.models.video import Video
        from app.models.mongodb.video_distribution import VideoDistribution, VideoDistributionRepository
        from app.models.mongodb.video_timeline_emotion_count import VideoTimelineEmotionCount, VideoTimelineEmotionCountRepository
        from common.extensions import mongo_db

        if not video_list:
            return 0

        existing_ids = {
            v.youtube_url
            for v in Video.query.filter(
                Video.youtube_url.in_([v['youtube_id'] for v in video_list])
            ).all()
        }

        dist_repo = VideoDistributionRepository(mongo_db)
        timeline_repo = VideoTimelineEmotionCountRepository(mongo_db)
        saved = 0

        for vd in video_list:
            if vd['youtube_id'] in existing_ids:
                continue
            try:
                video = Video(
                    youtube_url=vd['youtube_id'],
                    title=vd['title'][:255],
                    channel_name=vd['channel_name'][:100],
                    category=target_category,
                    duration=vd['duration'],
                    view_count=0,
                    is_deleted=0,
                )
                db.session.add(video)
                db.session.flush()

                dist_repo.upsert(VideoDistribution(video_id=video.video_id))
                timeline_repo.upsert(VideoTimelineEmotionCount(video_id=video.video_id))
                saved += 1

            except Exception as e:
                logger.error(f"영상 저장 오류 ({vd['youtube_id']}): {e}")

        return saved

    def execute(self):
        try:
            self.api_key = current_app.config.get('YOUTUBE_API_KEY')
            if not self.api_key:
                logger.error("YouTube API 키가 설정되지 않았습니다.")
                return

            self.quota_used = 0
            logger.info("카테고리 보충 수집 시작...")

            counts = self._check_category_counts()
            logger.info(
                "카테고리별 현재 영상 수: " +
                ', '.join(f"{k.value}={v}" for k, v in sorted(counts.items(), key=lambda x: x[1]))
            )

            targets = self._priority_targets(counts)
            logger.info(f"보충 대상 카테고리: {[(g.value, cnt) for g, cnt in targets]}")

            total_saved = 0
            search_calls = 0

            for genre, current_count in targets:
                if search_calls >= MAX_SEARCH_CALLS:
                    logger.warning(f"최대 검색 호출 수({MAX_SEARCH_CALLS}) 도달. 수집 종료.")
                    break
                if self.quota_used > MAX_SEARCH_CALLS * 100:
                    logger.warning("Quota 한도 도달. 수집 종료.")
                    break

                queries = CATEGORY_SEARCH_QUERIES.get(genre, [])
                shortage = TARGET_MIN_COUNT - current_count

                if shortage > 10:
                    num_queries = min(3, len(queries))
                elif shortage > 5:
                    num_queries = min(2, len(queries))
                else:
                    num_queries = 1

                genre_saved = 0
                for query in queries[:num_queries]:
                    if search_calls >= MAX_SEARCH_CALLS:
                        break

                    video_ids = self._search_video_ids(query)
                    search_calls += 1

                    if not video_ids:
                        continue

                    details = self._fetch_video_details(video_ids)
                    saved = self._save_videos(details, genre)
                    genre_saved += saved
                    logger.info(f"  [{genre.value}] '{query}' → {saved}개 저장")

                total_saved += genre_saved
                logger.info(
                    f"카테고리 [{genre.value}] 완료: {genre_saved}개 추가 "
                    f"(기존 {current_count} → 약 {current_count + genre_saved}개)"
                )

            db.session.commit()
            logger.info(
                f"카테고리 보충 완료: 총 {total_saved}개 저장 | "
                f"search 호출 {search_calls}회 | 총 quota 사용 {self.quota_used}"
            )

        except Exception as e:
            db.session.rollback()
            logger.error(f"카테고리 보충 수집 중 오류: {e}", exc_info=True)
            raise
