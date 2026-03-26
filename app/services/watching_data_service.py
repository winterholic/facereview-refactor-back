from typing import Dict, List
from datetime import datetime
import common.extensions as extensions
from app.models.mongodb.youtube_watching_data import YoutubeWatchingData, YoutubeWatchingDataRepository, EmotionPercentages, ClientInfo
from app.models.mongodb.video_distribution import VideoDistribution, VideoDistributionRepository
from app.models.mongodb.video_timeline_emotion_count import VideoTimelineEmotionCount, VideoTimelineEmotionCountRepository
from common.utils.logging_utils import get_logger

logger = get_logger('watching_data_service')


class WatchingDataService:
    @staticmethod
    def save_watching_data(video_view_log_id: str, duration: int = None, client_info_dict: Dict = None, cached_data: Dict = None):
        if not cached_data:
            logger.info(f"캐시 데이터 없음: {video_view_log_id}")
            return

        user_id = cached_data['user_id']
        video_id = cached_data['video_id']
        video_duration = duration or cached_data.get('duration')

        watching_data_repo = YoutubeWatchingDataRepository(extensions.mongo_db)

        #NOTE: upsert_frame이 실시간으로 쌓은 MongoDB 도큐먼트에서 타임라인 데이터를 읽어 통계 계산
        existing = watching_data_repo.find_by_video_view_log_id(video_view_log_id)
        if not existing or not existing.emotion_score_timeline:
            logger.info(f"시청 타임라인 데이터 없음: {video_view_log_id}")
            return

        emotion_stats = WatchingDataService._calculate_emotion_statistics_from_timeline(
            existing.emotion_score_timeline
        )
        frame_count = len(existing.emotion_score_timeline)
        completion_rate = WatchingDataService._calculate_completion_rate_from_count(frame_count, video_duration)

        emotion_percentages = EmotionPercentages(
            neutral=emotion_stats['emotion_percentages']['neutral'],
            happy=emotion_stats['emotion_percentages']['happy'],
            surprise=emotion_stats['emotion_percentages']['surprise'],
            sad=emotion_stats['emotion_percentages']['sad'],
            angry=emotion_stats['emotion_percentages']['angry']
        )

        client_info = ClientInfo()
        if client_info_dict:
            client_info.ip_address = client_info_dict.get('ip_address')
            client_info.user_agent = client_info_dict.get('user_agent')
            client_info.device_os = client_info_dict.get('device_os')
            client_info.device_browser = client_info_dict.get('device_browser')
            client_info.is_mobile = client_info_dict.get('is_mobile', False)

        watching_data = YoutubeWatchingData(
            user_id=user_id,
            video_id=video_id,
            video_view_log_id=video_view_log_id,
            created_at=existing.created_at,
            completion_rate=completion_rate,
            dominant_emotion=emotion_stats['dominant_emotion'],
            emotion_percentages=emotion_percentages,
            most_emotion_timeline=existing.most_emotion_timeline,
            emotion_score_timeline=existing.emotion_score_timeline,
            client_info=client_info
        )

        watching_data_repo.finalize(watching_data)
        logger.info(f"시청 데이터 저장 완료: {video_view_log_id}")

        #NOTE: video_distribution 평균/추천점수 업데이트 (기존 로직 유지)
        #NOTE: watch_frame에서 emotion_counts는 실시간 증가, 여기서는 평균 계산
        video_dist_repo = VideoDistributionRepository(extensions.mongo_db)
        WatchingDataService._update_video_distribution(
            video_dist_repo,
            watching_data_repo,
            video_id
        )

        #NOTE: video_timeline_emotion_count는 watch_frame에서 실시간 업데이트되므로 생략
        #NOTE: (중복 집계 방지 - dedupe 로직 적용됨)

    @staticmethod
    def _calculate_emotion_statistics(frames: List[Dict]) -> Dict:
        if not frames:
            return {
                'emotion_percentages': {
                    'neutral': 0.0,
                    'happy': 0.0,
                    'surprise': 0.0,
                    'sad': 0.0,
                    'angry': 0.0
                },
                'dominant_emotion': 'neutral'
            }

        emotion_sums = {
            'neutral': 0.0,
            'happy': 0.0,
            'surprise': 0.0,
            'sad': 0.0,
            'angry': 0.0
        }

        for frame in frames:
            emotion_pct = frame['emotion_percentages']
            for emotion in emotion_sums.keys():
                emotion_sums[emotion] += emotion_pct.get(emotion, 0.0)

        frame_count = len(frames)
        emotion_percentages = {
            emotion: round(sum_val / frame_count / 100.0, 3)
            for emotion, sum_val in emotion_sums.items()
        }

        dominant_emotion = max(emotion_percentages, key=emotion_percentages.get)

        return {
            'emotion_percentages': emotion_percentages,
            'dominant_emotion': dominant_emotion
        }

    @staticmethod
    def _calculate_completion_rate(frames: List[Dict], duration: int = None) -> float:
        if not frames:
            return 0.0

        if not duration:
            #NOTE: duration이 없으면 기존 로직 사용 (1000개 기준)
            return min(1.0, len(frames) / 1000.0)

        #NOTE: 0.1초(100ms) 단위로 프레임 전송 → 최대 프레임 개수 = duration * 10
        max_frame_count = duration * 10
        actual_frame_count = len(frames)

        completion_rate = actual_frame_count / max_frame_count if max_frame_count > 0 else 0.0

        #NOTE: 100%를 초과할 수 없음 (유저가 반복 재생할 경우 방지)
        return min(1.0, completion_rate)

    @staticmethod
    def _calculate_emotion_statistics_from_timeline(emotion_score_timeline: Dict) -> Dict:
        #NOTE: emotion_score_timeline 형식: {centisecond_str: [neutral, happy, surprise, sad, angry]} (0~100 스케일)
        labels = ['neutral', 'happy', 'surprise', 'sad', 'angry']
        emotion_sums = {label: 0.0 for label in labels}

        for scores in emotion_score_timeline.values():
            for i, label in enumerate(labels):
                emotion_sums[label] += scores[i]

        frame_count = len(emotion_score_timeline)
        if frame_count == 0:
            return {
                'emotion_percentages': {label: 0.0 for label in labels},
                'dominant_emotion': 'neutral'
            }

        emotion_percentages = {
            label: round(emotion_sums[label] / frame_count / 100.0, 3)
            for label in labels
        }
        dominant_emotion = max(emotion_percentages, key=emotion_percentages.get)

        return {
            'emotion_percentages': emotion_percentages,
            'dominant_emotion': dominant_emotion
        }

    @staticmethod
    def _calculate_completion_rate_from_count(frame_count: int, duration: int = None) -> float:
        if frame_count == 0:
            return 0.0
        if not duration:
            return min(1.0, frame_count / 1000.0)
        #NOTE: 0.1초(100ms) 단위로 프레임 전송 → 최대 프레임 개수 = duration * 10
        max_frame_count = duration * 10
        return min(1.0, frame_count / max_frame_count if max_frame_count > 0 else 0.0)

    @staticmethod
    def _update_timeline_emotion_count(
        timeline_count_repo: VideoTimelineEmotionCountRepository,
        video_id: str,
        frames: List[Dict]
    ):
        try:
            for frame in frames:
                youtube_running_time = frame['youtube_running_time']
                most_emotion = frame['most_emotion']

                timeline_count_repo.increment_emotion(
                    video_id=video_id,
                    youtube_running_time=youtube_running_time,
                    emotion=most_emotion
                )

            logger.info(f"타임라인 감정 카운트 업데이트 완료: {video_id}")
        except Exception as e:
            logger.error(f"타임라인 감정 카운트 업데이트 오류: {e}")

    @staticmethod
    def _update_video_distribution(
        video_dist_repo: VideoDistributionRepository,
        watching_data_repo: YoutubeWatchingDataRepository,
        video_id: str
    ):
        try:
            all_watching_data = watching_data_repo.find_by_video_id(video_id, limit=1000)

            if not all_watching_data:
                return

            emotion_sums = {
                'neutral': 0.0,
                'happy': 0.0,
                'surprise': 0.0,
                'sad': 0.0,
                'angry': 0.0
            }
            completion_rate_sum = 0.0
            count = len(all_watching_data)

            for wd in all_watching_data:
                emotion_sums['neutral'] += wd.emotion_percentages.neutral
                emotion_sums['happy'] += wd.emotion_percentages.happy
                emotion_sums['surprise'] += wd.emotion_percentages.surprise
                emotion_sums['sad'] += wd.emotion_percentages.sad
                emotion_sums['angry'] += wd.emotion_percentages.angry
                completion_rate_sum += wd.completion_rate

            from app.models.mongodb.video_distribution import EmotionAverages, RecommendationScores

            emotion_averages = EmotionAverages(
                neutral=round(emotion_sums['neutral'] / count, 3),
                happy=round(emotion_sums['happy'] / count, 3),
                surprise=round(emotion_sums['surprise'] / count, 3),
                sad=round(emotion_sums['sad'] / count, 3),
                angry=round(emotion_sums['angry'] / count, 3)
            )

            recommendation_scores = RecommendationScores(
                neutral=round(emotion_averages.neutral * 2, 3),
                happy=round(emotion_averages.happy * 3, 3),
                surprise=round(emotion_averages.surprise * 4, 3),
                sad=round(emotion_averages.sad * 3, 3),
                angry=round(emotion_averages.angry * 3, 3)
            )

            scores_dict = {
                'neutral': recommendation_scores.neutral,
                'happy': recommendation_scores.happy,
                'surprise': recommendation_scores.surprise,
                'sad': recommendation_scores.sad,
                'angry': recommendation_scores.angry
            }
            dominant_emotion = max(scores_dict, key=scores_dict.get)

            video_distribution = VideoDistribution(
                video_id=video_id,
                average_completion_rate=round(completion_rate_sum / count, 3),
                emotion_averages=emotion_averages,
                recommendation_scores=recommendation_scores,
                dominant_emotion=dominant_emotion,
                updated_at=datetime.utcnow()
            )

            video_dist_repo.upsert(video_distribution)
            logger.info(f"영상 분포 업데이트 완료: {video_id}")

        except Exception as e:
            logger.error(f"영상 분포 업데이트 오류: {e}")
