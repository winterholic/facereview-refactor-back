from app.services.home_service import HomeService
from common.celery_app import celery_app
from common.scheduler.jobs import YoutubeCategoryFillJob, YoutubeTrendingJob
from common.utils.logging_utils import get_logger


logger = get_logger('scheduled_tasks')


@celery_app.task(name='common.tasks.scheduled_tasks.fetch_youtube_trending_videos')
def fetch_youtube_trending_videos():
    logger.info("YouTube 인기 동영상 수집 예약 작업 시작")
    YoutubeTrendingJob().execute()
    logger.info("YouTube 인기 동영상 수집 예약 작업 완료")


@celery_app.task(name='common.tasks.scheduled_tasks.fill_youtube_category_videos')
def fill_youtube_category_videos():
    logger.info("YouTube 카테고리 보충 예약 작업 시작")
    YoutubeCategoryFillJob().execute()
    logger.info("YouTube 카테고리 보충 예약 작업 완료")


@celery_app.task(name='common.tasks.scheduled_tasks.rebuild_recommendation_pool')
def rebuild_recommendation_pool():
    pool, _ = HomeService._build_and_cache_ranked_pool()
    logger.info(f"추천 풀 예약 재계산 완료: 상위 {len(pool)}개 영상")
    return {'video_count': len(pool)}
