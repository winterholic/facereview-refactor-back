from common.extensions import scheduler
from common.scheduler.jobs import YoutubeTrendingJob, YoutubeCategoryFillJob
from common.utils.logging_utils import get_logger

logger = get_logger('scheduler_tasks')


def register_scheduled_tasks():
    scheduler.add_job(
        id='fetch_youtube_trending_videos',
        func=execute_youtube_trending_job,
        trigger='cron',
        hour=6,
        minute=0,
        replace_existing=True
    )

    scheduler.add_job(
        id='fill_youtube_category_videos',
        func=execute_youtube_category_fill_job,
        trigger='cron',
        day_of_week='tue,fri',
        hour=3,
        minute=0,
        replace_existing=True
    )

    scheduler.add_job(
        id='refresh_home_cache',
        func=execute_home_cache_refresh,
        trigger='cron',
        hour=5,
        minute=0,
        replace_existing=True
    )

    logger.info("모든 스케줄 작업이 등록되었습니다.")
    logger.info("YouTube 인기 동영상 수집: 매일 06:00")
    logger.info("YouTube 카테고리 보충 수집: 매주 화·금 03:00")
    logger.info("홈 화면 Redis 캐시 갱신: 매일 05:00")


def execute_youtube_trending_job():
    with scheduler.app.app_context():
        try:
            logger.info("YouTube 인기 동영상 수집 작업 시작")
            job = YoutubeTrendingJob()
            job.execute()
            logger.info("YouTube 인기 동영상 수집 작업 완료")
        except Exception as e:
            logger.error(f"YouTube 인기 동영상 수집 작업 실패: {str(e)}", exc_info=True)


def execute_youtube_category_fill_job():
    with scheduler.app.app_context():
        try:
            logger.info("YouTube 카테고리 보충 수집 작업 시작")
            job = YoutubeCategoryFillJob()
            job.execute()
            logger.info("YouTube 카테고리 보충 수집 작업 완료")
        except Exception as e:
            logger.error(f"YouTube 카테고리 보충 수집 작업 실패: {str(e)}", exc_info=True)


def execute_home_cache_refresh():
    with scheduler.app.app_context():
        try:
            logger.info("홈 화면 Redis 캐시 갱신 작업 시작")
            from app.services.home_service import HomeService
            HomeService._build_and_cache_video_pool()
            HomeService._build_and_cache_category_videos()
            logger.info("홈 화면 Redis 캐시 갱신 작업 완료")
        except Exception as e:
            logger.error(f"홈 화면 Redis 캐시 갱신 작업 실패: {str(e)}", exc_info=True)
