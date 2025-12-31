import os


class CeleryConfig:

    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/1')

    broker_url = REDIS_URL
    broker_connection_retry_on_startup = True

    result_backend = REDIS_URL

    task_serializer = 'json'
    result_serializer = 'json'
    accept_content = ['json']
    timezone = 'Asia/Seoul'
    enable_utc = True

    result_expires = 3600

    task_acks_late = True
    task_reject_on_worker_lost = True

    worker_prefetch_multiplier = 1
    worker_max_tasks_per_child = 1000

    task_routes = {
        'common.tasks.watching_data_tasks.*': {'queue': 'watching_data'},
    }
