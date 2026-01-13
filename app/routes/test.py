from flask import current_app
from flask_smorest import Blueprint
import sentry_sdk

from app.schemas.common_schema import SuccessResponseSchema
from common.decorator.auth_decorators import public_route
from common.scheduler.jobs import YoutubeTrendingJob, VideoDistributionHistoryJob
from common.utils.logging_utils import get_logger

logger = get_logger('test_routes')

test_blueprint = Blueprint(
    'test',
    __name__,
    url_prefix='/api/v2/test',
    description='테스트용 API (개발 환경 전용)'
)


@test_blueprint.route('/scheduler/youtube-trending', methods=['POST'])
@public_route
@test_blueprint.response(200, SuccessResponseSchema)
def test_youtube_trending_job():
    try:
        logger.info("YouTube 인기 동영상 수집 테스트 시작")

        job = YoutubeTrendingJob()
        job.execute()

        logger.info("YouTube 인기 동영상 수집 테스트 완료")

        return {
            "result": "success",
            "message": "YouTube 인기 동영상 수집 작업이 성공적으로 실행되었습니다. 로그를 확인하세요."
        }
    except Exception as e:
        logger.error(f"YouTube 인기 동영상 수집 테스트 실패: {str(e)}", exc_info=True)
        return {
            "result": "error",
            "message": f"작업 실행 중 오류 발생: {str(e)}"
        }, 500


@test_blueprint.route('/scheduler/video-distribution-history', methods=['POST'])
@public_route
@test_blueprint.response(200, SuccessResponseSchema)
def test_video_distribution_history_job():
    try:
        logger.info("Video Distribution History 생성 테스트 시작")

        job = VideoDistributionHistoryJob()
        job.execute()

        logger.info("Video Distribution History 생성 테스트 완료")

        return {
            "result": "success",
            "message": "Video Distribution History 생성 작업이 성공적으로 실행되었습니다. 로그를 확인하세요."
        }
    except Exception as e:
        logger.error(f"Video Distribution History 생성 테스트 실패: {str(e)}", exc_info=True)
        return {
            "result": "error",
            "message": f"작업 실행 중 오류 발생: {str(e)}"
        }, 500


@test_blueprint.route('/scheduler/status', methods=['GET'])
@public_route
@test_blueprint.response(200, SuccessResponseSchema)
def get_scheduler_status():
    try:
        from common.extensions import scheduler

        jobs_info = []
        for job in scheduler.get_jobs():
            jobs_info.append({
                'id': job.id,
                'name': job.name,
                'trigger': str(job.trigger),
                'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None
            })

        return {
            "result": "success",
            "message": "스케줄러 상태 조회 완료",
            "data": {
                "running": scheduler.running,
                "jobs": jobs_info,
                "jobs_count": len(jobs_info)
            }
        }
    except Exception as e:
        logger.error(f"스케줄러 상태 조회 실패: {str(e)}", exc_info=True)
        return {
            "result": "error",
            "message": f"스케줄러 상태 조회 중 오류 발생: {str(e)}"
        }, 500


@test_blueprint.route('/config/check', methods=['GET'])
@public_route
@test_blueprint.response(200, SuccessResponseSchema)
def check_config():
    try:
        youtube_api_key_exists = bool(current_app.config.get('YOUTUBE_API_KEY'))
        sentry_dsn_exists = bool(current_app.config.get('SENTRY_DSN'))

        return {
            "result": "success",
            "message": "설정 확인 완료",
            "data": {
                "YOUTUBE_API_KEY": "설정됨" if youtube_api_key_exists else "미설정",
                "MONGO_DB_NAME": current_app.config.get('MONGO_DB_NAME'),
                "SCHEDULER_TIMEZONE": current_app.config.get('SCHEDULER_TIMEZONE'),
                "SENTRY_DSN": "설정됨" if sentry_dsn_exists else "미설정",
                "SENTRY_ENVIRONMENT": current_app.config.get('SENTRY_ENVIRONMENT'),
            }
        }
    except Exception as e:
        logger.error(f"설정 확인 실패: {str(e)}", exc_info=True)
        return {
            "result": "error",
            "message": f"설정 확인 중 오류 발생: {str(e)}"
        }, 500


@test_blueprint.route('/sentry/test-error', methods=['GET'])
@public_route
@test_blueprint.response(200, SuccessResponseSchema)
def test_sentry_error():
    try:
        sentry_sdk.capture_message("Sentry 테스트 메시지", level="info")

        raise Exception("Sentry 테스트 에러입니다. 정상적으로 작동한다면 Sentry 대시보드에서 확인할 수 있습니다.")
    except Exception as e:
        sentry_sdk.capture_exception(e)
        raise


@test_blueprint.route('/sentry/test-message', methods=['GET'])
@public_route
@test_blueprint.response(200, SuccessResponseSchema)
def test_sentry_message():
    sentry_sdk.capture_message("Sentry 테스트 메시지 전송 성공", level="info")

    return {
        "result": "success",
        "message": "Sentry 메시지가 전송되었습니다. Sentry 대시보드를 확인하세요."
    }
