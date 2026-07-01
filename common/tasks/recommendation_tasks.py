from common.celery_app import celery_app
from common.utils.logging_utils import get_logger

logger = get_logger('recommendation_tasks')


@celery_app.task(
    name='recommendation.rebuild_pool',
    bind=True,
    max_retries=2,
    default_retry_delay=120
)
def rebuild_recommendation_pool_task(self):
    #NOTE: 경주마 2단 추천 Tier1 - 영상 본질 점수 상위 풀/카테고리 리스트를 주기적으로 재계산해 Redis 갱신
    try:
        from app.services.home_service import HomeService
        pool, _ = HomeService._build_and_cache_ranked_pool()
        logger.info(f"추천 풀 재계산 완료: {len(pool)}개 영상")
        return {'status': 'success', 'pool_size': len(pool)}
    except Exception as exc:
        logger.error(f"추천 풀 재계산 실패: {exc}", exc_info=True)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.error("추천 풀 재계산 최대 재시도 초과")
            return {'status': 'error', 'message': str(exc)}
