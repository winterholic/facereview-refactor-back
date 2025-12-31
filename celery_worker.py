"""
Celery Worker 실행 스크립트
Flask app context와 함께 Celery worker를 실행
"""

from app import create_app
from common.extensions import celery

# Flask app 생성
app = create_app()

# Flask app context를 Celery에 연결
celery.conf.update(app.config)


if __name__ == '__main__':
    # Celery worker 실행
    # 명령어: python celery_worker.py worker --loglevel=info
    celery.start()
