from datetime import datetime
from typing import List
from common.utils.logging_utils import get_logger

from common.extensions import mongo_db
from app.models.mongodb.video_distribution import VideoDistributionRepository, VideoDistribution
from app.models.mongodb.video_distribution_history import (
    VideoDistributionHistoryRepository,
    VideoDistributionHistory,
    EmotionAveragesHistory,
    RecommendationScoresHistory
)

logger = get_logger('video_distribution_history_job')


class VideoDistributionHistoryJob:

    def __init__(self):
        self.distribution_repo = None
        self.history_repo = None

    def _convert_to_history(self, distribution: VideoDistribution, recorded_at: datetime) -> VideoDistributionHistory:
        emotion_averages_history = EmotionAveragesHistory(
            neutral=distribution.emotion_averages.neutral,
            happy=distribution.emotion_averages.happy,
            surprise=distribution.emotion_averages.surprise,
            sad=distribution.emotion_averages.sad,
            angry=distribution.emotion_averages.angry
        )

        recommendation_scores_history = RecommendationScoresHistory(
            neutral=distribution.recommendation_scores.neutral,
            happy=distribution.recommendation_scores.happy,
            surprise=distribution.recommendation_scores.surprise,
            sad=distribution.recommendation_scores.sad,
            angry=distribution.recommendation_scores.angry
        )

        return VideoDistributionHistory(
            video_id=distribution.video_id,
            recorded_at=recorded_at,
            average_completion_rate=distribution.average_completion_rate,
            emotion_averages=emotion_averages_history,
            recommendation_scores=recommendation_scores_history,
            dominant_emotion=distribution.dominant_emotion
        )

    def execute(self):
        try:
            self.distribution_repo = VideoDistributionRepository(mongo_db)
            self.history_repo = VideoDistributionHistoryRepository(mongo_db)

            logger.info("Video Distribution History 생성 시작...")

            recorded_at = datetime.utcnow()

            all_distributions = self.distribution_repo.collection.find({})

            saved_count = 0
            for dist_doc in all_distributions:
                try:
                    distribution = VideoDistribution.from_dict(dist_doc)

                    history = self._convert_to_history(distribution, recorded_at)

                    self.history_repo.insert(history)
                    saved_count += 1

                except Exception as e:
                    logger.error(f"히스토리 저장 오류 (video_id: {dist_doc.get('video_id')}): {str(e)}")
                    continue

            logger.info(f"Video Distribution History 생성 완료: {saved_count}개 저장")

            # NOTE: 90일 이전 히스토리 삭제 (선택적)
            try:
                self.history_repo.delete_old_records(days=90)
                logger.info("90일 이전 오래된 히스토리 삭제 완료")
            except Exception as e:
                logger.error(f"오래된 히스토리 삭제 중 오류: {str(e)}")

        except Exception as e:
            logger.error(f"Video Distribution History 생성 중 오류: {str(e)}")
