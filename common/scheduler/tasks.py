from datetime import datetime, timedelta
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

    #NOTE: 경주마 2단 추천 Tier1 - 30분마다 Celery로 영상 본질 점수 상위 풀 재계산 (무거운 계산 오프라인화)
    #      next_run_time을 부팅 직후로 당겨 콜드스타트(첫 요청이 동기 빌드로 느려짐) 방지
    scheduler.add_job(
        id='rebuild_recommendation_pool',
        func=trigger_recommendation_pool_rebuild,
        trigger='interval',
        minutes=30,
        next_run_time=datetime.now() + timedelta(seconds=15),
        replace_existing=True
    )

    logger.info("모든 스케줄 작업이 등록되었습니다.")
    logger.info("YouTube 인기 동영상 수집: 매일 06:00")
    logger.info("YouTube 카테고리 보충 수집: 매주 화·금 03:00")
    logger.info("추천 풀(base_score 상위) 재계산: 30분 간격")


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


def trigger_recommendation_pool_rebuild():
    #NOTE: 무거운 계산은 Celery 워커로 오프로드. 워커/브로커 장애 시 앱 컨텍스트에서 동기 폴백
    try:
        from common.tasks.recommendation_tasks import rebuild_recommendation_pool_task
        rebuild_recommendation_pool_task.delay()
        logger.info("추천 풀 재계산 Celery 태스크 enqueue")
    except Exception as e:
        logger.warning(f"추천 풀 재계산 enqueue 실패 → 동기 폴백: {e}")
        with scheduler.app.app_context():
            try:
                from app.services.home_service import HomeService
                HomeService._build_and_cache_ranked_pool()
                logger.info("추천 풀 재계산 동기 폴백 완료")
            except Exception as inner:
                logger.error(f"추천 풀 재계산 동기 폴백 실패: {inner}", exc_info=True)
