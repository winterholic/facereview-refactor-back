import os
from urllib.parse import quote

from celery.schedules import crontab


def build_redis_url(env):
    explicit_url = env.get('REDIS_URL')
    if explicit_url:
        return explicit_url

    host = env.get('REDIS_HOST', 'localhost')
    port = env.get('REDIS_PORT', '6379')
    database = env.get('REDIS_DB', '1')
    password = env.get('REDIS_PASSWORD')
    credentials = f":{quote(password, safe='')}@" if password else ''
    return f"redis://{credentials}{host}:{port}/{database}"


class CeleryConfig:

    REDIS_URL = build_redis_url(os.environ)

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

    beat_schedule = {
        'fetch-youtube-trending-videos': {
            'task': 'common.tasks.scheduled_tasks.fetch_youtube_trending_videos',
            'schedule': crontab(hour=6, minute=0),
        },
        'fill-youtube-category-videos': {
            'task': 'common.tasks.scheduled_tasks.fill_youtube_category_videos',
            'schedule': crontab(day_of_week='tue,fri', hour=3, minute=0),
        },
        'rebuild-recommendation-pool': {
            'task': 'common.tasks.scheduled_tasks.rebuild_recommendation_pool',
            'schedule': 30 * 60,
        },
    }
