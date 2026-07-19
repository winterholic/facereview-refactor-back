from common.celery_app import celery_app
from app.services.watching_data_service import WatchingDataService
from common.utils.logging_utils import get_logger

logger = get_logger('watching_data_tasks')


@celery_app.task(
    name='watching_data.save',
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
def save_watching_data_task(self, video_view_log_id: str, duration: int = None, client_info: dict = None, cached_data: dict = None):
    try:
        logger.debug(f"시청 데이터 저장 시작: {video_view_log_id}")

        WatchingDataService.save_watching_data(
            video_view_log_id=video_view_log_id,
            duration=duration,
            client_info_dict=client_info,
            cached_data=cached_data
        )

        logger.info(f"시청 데이터 저장 완료: {video_view_log_id}")

        return {
            'status': 'success',
            'video_view_log_id': video_view_log_id,
            'message': 'Watching data saved successfully'
        }

    except Exception as exc:
        logger.error(f"시청 데이터 저장 실패: {exc}")

        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.error(f"시청 데이터 저장 최대 재시도 초과: {video_view_log_id}")
            return {
                'status': 'error',
                'video_view_log_id': video_view_log_id,
                'message': f'Failed after max retries: {str(exc)}'
            }
