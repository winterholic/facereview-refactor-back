import os

from app import create_app
from common.celery_app import create_worker_celery

celery = create_worker_celery(
    create_app,
    os.getenv('FLASK_ENV', 'production'),
)


if __name__ == '__main__':
    celery.start()
