from datetime import datetime
from app.models.mongodb.youtube_watching_data import YoutubeWatchingDataRepository
from app.models.mongodb.video_distribution import VideoDistribution, VideoDistributionRepository, MIN_RELIABLE_FRAMES
from common.utils.logging_utils import get_logger

logger = get_logger('watching_data_service')


class WatchingDataService:
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

            #NOTE: 대표 감정은 화면의 감정 비율과 일치해야 하므로 가중 점수가 아닌 원본 평균에서 고른다.
            averages_dict = {
                'neutral': emotion_averages.neutral,
                'happy': emotion_averages.happy,
                'surprise': emotion_averages.surprise,
                'sad': emotion_averages.sad,
                'angry': emotion_averages.angry
            }
            #NOTE: 표본 신뢰도는 세션 수가 아니라 실제 관찰 프레임 수로 판단한다.
            total_frames_observed = sum(len(wd.emotion_score_timeline) for wd in all_watching_data)
            dominant_emotion = (
                max(averages_dict, key=averages_dict.get)
                if total_frames_observed >= MIN_RELIABLE_FRAMES else None
            )

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
