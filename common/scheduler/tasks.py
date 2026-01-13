"""
스케줄 작업 정의 및 등록
- YouTube API를 사용한 인기 동영상 수집
- Video Distribution History 생성
"""

from flask import current_app
from common.extensions import scheduler
from common.scheduler.jobs import YoutubeTrendingJob, VideoDistributionHistoryJob
from common.utils.logging_utils import get_logger

logger = get_logger('scheduler_tasks')


def register_scheduled_tasks():
    """
    모든 스케줄 작업을 등록하는 함수
    """
    # 매일 새벽 6시에 YouTube 인기 동영상 수집
    scheduler.add_job(
        id='fetch_youtube_trending_videos',
        func=execute_youtube_trending_job,
        trigger='cron',
        hour=6,
        minute=0,
        replace_existing=True
    )

    # 매일 새벽 5시에 Video Distribution History 생성
    scheduler.add_job(
        id='create_video_distribution_history',
        func=execute_video_distribution_history_job,
        trigger='cron',
        hour=5,
        minute=0,
        replace_existing=True
    )

    logger.info("모든 스케줄 작업이 등록되었습니다.")
    logger.info("YouTube 인기 동영상 수집: 매일 06:00")
    logger.info("Video Distribution History 생성: 매일 05:00")


def execute_youtube_trending_job():
    """YouTube 인기 동영상 수집 Job 실행 (Flask 앱 컨텍스트 내에서)"""
    with scheduler.app.app_context():
        try:
            logger.info("YouTube 인기 동영상 수집 작업 시작")
            job = YoutubeTrendingJob()
            job.execute()
            logger.info("YouTube 인기 동영상 수집 작업 완료")
        except Exception as e:
            logger.error(f"YouTube 인기 동영상 수집 작업 실패: {str(e)}", exc_info=True)


def execute_video_distribution_history_job():
    """Video Distribution History 생성 Job 실행 (Flask 앱 컨텍스트 내에서)"""
    with scheduler.app.app_context():
        try:
            logger.info("Video Distribution History 생성 작업 시작")
            job = VideoDistributionHistoryJob()
            job.execute()
            logger.info("Video Distribution History 생성 작업 완료")
        except Exception as e:
            logger.error(f"Video Distribution History 생성 작업 실패: {str(e)}", exc_info=True)
