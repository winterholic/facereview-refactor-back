import re
import isodate
from datetime import datetime
from typing import List, Dict
import requests
from flask import current_app
from common.utils.logging_utils import get_logger

from common.extensions import db
from common.decorator.db_decorators import transactional
from common.enum.youtube_genre import GenreEnum

logger = get_logger('youtube_trending_job')


YOUTUBE_CATEGORY_MAPPING = {
    '1': GenreEnum.ETC,          # Film & Animation
    '2': GenreEnum.ETC,          # Autos & Vehicles
    '10': GenreEnum.MUSIC,       # Music
    '15': GenreEnum.ANIMAL,      # Pets & Animals
    '17': GenreEnum.SPORTS,      # Sports
    '19': GenreEnum.TRAVEL,      # Travel & Events
    '20': GenreEnum.GAME,        # Gaming
    '22': GenreEnum.ETC,         # People & Blogs
    '23': GenreEnum.COMEDY,      # Comedy
    '24': GenreEnum.SHOW,        # Entertainment
    '25': GenreEnum.INFORMATION, # News & Politics
    '26': GenreEnum.BEAUTY,      # Howto & Style
    '27': GenreEnum.INFORMATION, # Education
    '28': GenreEnum.INFORMATION, # Science & Technology
}

KEYWORD_CATEGORY_MAPPING = {
    GenreEnum.DRAMA: ['드라마', '연속극', 'drama', 'series', '시리즈'],
    GenreEnum.EATING: ['먹방', '음식', '맛집', 'mukbang', 'eating', 'food', 'asmr'],
    GenreEnum.TRAVEL: ['여행', '관광', 'travel', 'tour', 'trip', '세계여행', 'vlog'],
    GenreEnum.COOK: ['요리', '레시피', '쿠킹', 'cooking', 'recipe', '만들기', 'cook'],
    GenreEnum.SHOW: ['예능', '버라이어티', 'variety', 'show', '토크쇼', '예능'],
    GenreEnum.INFORMATION: ['정보', '교육', '강의', 'education', 'tutorial', '배우기', 'learn', '뉴스', 'news'],
    GenreEnum.HORROR: ['공포', '호러', 'horror', 'scary', '무서운', '귀신', '스릴러', 'thriller'],
    GenreEnum.EXERCISE: ['운동', '헬스', '피트니스', 'exercise', 'fitness', 'workout', 'gym', '요가', 'yoga', '다이어트', 'diet'],
    GenreEnum.VLOG: ['일상', '브이로그', 'vlog', 'daily', '데일리', 'daily life', '하루', '루틴', 'routine'],
    GenreEnum.GAME: ['게임', 'game', 'gaming', '게이밍', '롤', 'lol', '배그', 'pubg'],
    GenreEnum.SPORTS: ['스포츠', '운동', 'sports', '축구', '야구', 'soccer', 'baseball', '농구'],
    GenreEnum.MUSIC: ['음악', '노래', 'music', 'song', 'mv', '뮤직비디오', 'kpop'],
    GenreEnum.ANIMAL: ['동물', '강아지', '고양이', 'animal', 'pet', 'dog', 'cat', '펫'],
    GenreEnum.BEAUTY: ['뷰티', '화장', '메이크업', 'beauty', 'makeup', '패션', 'fashion'],
    GenreEnum.COMEDY: ['코미디', '웃긴', '개그', 'comedy', 'funny', 'humor', '유머'],
}


class YoutubeTrendingJob:
    def __init__(self):
        self.api_key = None

    def _fetch_youtube_api(self, region_code: str = 'KR', max_results: int = 50, max_pages: int = 4) -> List[Dict]:
        videos = []
        page_token = None

        try:
            url = 'https://www.googleapis.com/youtube/v3/videos'

            for page in range(max_pages):
                params = {
                    'part': 'snippet,contentDetails,statistics',
                    'chart': 'mostPopular',
                    'regionCode': region_code,
                    'maxResults': max_results,
                    'key': self.api_key
                }

                if page_token:
                    params['pageToken'] = page_token

                response = requests.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                for item in data.get('items', []):
                    video_id = item.get('id')
                    snippet = item.get('snippet', {})
                    content_details = item.get('contentDetails', {})
                    statistics = item.get('statistics', {})

                    duration_iso = content_details.get('duration', 'PT0S')
                    try:
                        duration_seconds = int(isodate.parse_duration(duration_iso).total_seconds())
                    except:
                        duration_seconds = 0

                    video_info = {
                        'youtube_id': video_id,
                        'title': snippet.get('title', ''),
                        'channel_name': snippet.get('channelTitle', ''),
                        'category_id': snippet.get('categoryId', ''),
                        'tags': snippet.get('tags', []),
                        'description': snippet.get('description', ''),
                        'duration': duration_seconds,
                        'view_count': int(statistics.get('viewCount', 0)),
                    }

                    videos.append(video_info)

                page_token = data.get('nextPageToken')
                if not page_token:
                    break

                logger.info(f"YouTube API 페이지 {page + 1}/{max_pages} 완료 (현재 {len(videos)}개)")

        except requests.RequestException as e:
            logger.error(f"YouTube API 호출 오류: {str(e)}")
        except Exception as e:
            logger.error(f"인기 동영상 파싱 오류: {str(e)}")

        return videos

    def _classify_category_by_keywords(self, title: str, tags: List[str], description: str) -> GenreEnum:
        text = (title + ' ' + ' '.join(tags) + ' ' + description).lower()

        category_scores = {}
        for category, keywords in KEYWORD_CATEGORY_MAPPING.items():
            score = 0
            for keyword in keywords:
                score += text.count(keyword.lower())
            category_scores[category] = score

        if category_scores:
            best_category = max(category_scores, key=category_scores.get)
            if category_scores[best_category] > 0:
                return best_category

        return GenreEnum.ETC

    def _map_youtube_category(self, youtube_category_id: str, title: str, tags: List[str], description: str) -> GenreEnum:
        mapped_category = YOUTUBE_CATEGORY_MAPPING.get(youtube_category_id, GenreEnum.ETC)

        if mapped_category == GenreEnum.ETC:
            mapped_category = self._classify_category_by_keywords(title, tags, description)

        return mapped_category

    def execute(self):
        try:
            from app.models.video import Video
            from app.models.mongodb.video_distribution import VideoDistribution, VideoDistributionRepository
            from app.models.mongodb.video_timeline_emotion_count import VideoTimelineEmotionCount, VideoTimelineEmotionCountRepository
            from common.extensions import mongo_db

            self.api_key = current_app.config.get('YOUTUBE_API_KEY')
            if not self.api_key:
                logger.error("YouTube API 키가 설정되지 않았습니다.")
                return

            logger.info("YouTube 인기 동영상 수집 시작...")

            all_videos = self._fetch_youtube_api(region_code='KR', max_results=50, max_pages=4)

            if not all_videos:
                logger.warning("가져온 동영상이 없습니다.")
                return

            youtube_ids = [video['youtube_id'] for video in all_videos]

            existing_videos = Video.query.filter(
                Video.youtube_url.in_(youtube_ids)
            ).all()
            existing_youtube_urls = {video.youtube_url for video in existing_videos}

            new_videos = [
                video for video in all_videos
                if video['youtube_id'] not in existing_youtube_urls
            ]

            logger.info(f"전체 {len(all_videos)}개 중 신규 {len(new_videos)}개 발견")

            saved_count = 0
            mongo_saved_count = 0

            video_dist_repo = VideoDistributionRepository(mongo_db)
            timeline_repo = VideoTimelineEmotionCountRepository(mongo_db)

            for video_data in new_videos:
                try:
                    category = self._map_youtube_category(
                        youtube_category_id=video_data['category_id'],
                        title=video_data['title'],
                        tags=video_data['tags'],
                        description=video_data['description']
                    )

                    new_video = Video(
                        youtube_url=video_data['youtube_id'],
                        title=video_data['title'][:255],
                        channel_name=video_data['channel_name'][:100],
                        category=category,
                        duration=video_data['duration'],
                        view_count=0,
                        is_deleted=0
                    )

                    db.session.add(new_video)
                    db.session.flush()

                    video_distribution = VideoDistribution(
                        video_id=new_video.video_id
                    )
                    video_dist_repo.upsert(video_distribution)

                    timeline_emotion = VideoTimelineEmotionCount(
                        video_id=new_video.video_id
                    )
                    timeline_repo.upsert(timeline_emotion)

                    saved_count += 1
                    mongo_saved_count += 1

                except Exception as e:
                    logger.error(f"동영상 저장 오류 ({video_data['youtube_id']}): {str(e)}")
                    continue

            db.session.commit()

            logger.info(f"YouTube 인기 동영상 수집 완료: MySQL {saved_count}개, MongoDB {mongo_saved_count}개 저장")

        except Exception as e:
            db.session.rollback()
            logger.error(f"YouTube 인기 동영상 수집 중 오류: {str(e)}", exc_info=True)
            raise
