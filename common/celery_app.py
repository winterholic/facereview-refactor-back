"""
Celery Application
Flask와 통합된 Celery 앱
"""

from celery import Celery


def create_celery_app(app=None):
    """
    Flask 앱과 통합된 Celery 앱 생성

    Args:
        app: Flask application instance (optional)

    Returns:
        Celery: Celery application instance
    """
    celery = Celery(
        'facereview',
        broker=None,  # config에서 설정
        backend=None,  # config에서 설정
        include=['common.tasks.watching_data_tasks']  # task 모듈들
    )

    # Celery 설정 로드
    from common.config.celery_config import CeleryConfig
    celery.config_from_object(CeleryConfig)

    if app:
        # Flask app context에서 실행되도록 설정
        class ContextTask(celery.Task):
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)

        celery.Task = ContextTask

    return celery


# Celery 인스턴스 생성 (Flask app 없이)
# Flask app은 나중에 init_app에서 설정
celery_app = create_celery_app()
