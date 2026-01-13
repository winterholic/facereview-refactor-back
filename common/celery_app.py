"""
Celery Application
Flask와 통합된 Celery 앱
"""

import os
from celery import Celery
import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration


def create_celery_app(app=None):
    """
    Flask 앱과 통합된 Celery 앱 생성

    Args:
        app: Flask application instance (optional)

    Returns:
        Celery: Celery application instance
    """
    sentry_dsn = os.getenv('SENTRY_DSN')
    if sentry_dsn:
        sentry_sdk.init(
            dsn=sentry_dsn,
            environment=os.getenv('SENTRY_ENVIRONMENT', 'development'),
            traces_sample_rate=float(os.getenv('SENTRY_TRACES_SAMPLE_RATE', '1.0')),
            integrations=[CeleryIntegration()],
            send_default_pii=False,
            attach_stacktrace=True,
        )

    celery = Celery(
        'facereview',
        broker=None,
        backend=None,
        include=['common.tasks.watching_data_tasks']
    )

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
