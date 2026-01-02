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
def save_watching_data_task(self, video_view_log_id: str, duration: int = None, client_info: dict = None):
    try:
        logger.debug(f"Saving watching data: {video_view_log_id}")

        WatchingDataService.save_watching_data(
            video_view_log_id=video_view_log_id,
            duration=duration,
            client_info_dict=client_info
        )

        logger.info(f"Successfully saved watching data: {video_view_log_id}")

        return {
            'status': 'success',
            'video_view_log_id': video_view_log_id,
            'message': 'Watching data saved successfully'
        }

    except Exception as exc:
        logger.error(f"Error saving watching data: {exc}")

        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for {video_view_log_id}")
            return {
                'status': 'error',
                'video_view_log_id': video_view_log_id,
                'message': f'Failed after max retries: {str(exc)}'
            }
