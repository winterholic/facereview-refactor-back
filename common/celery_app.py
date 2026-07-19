from celery import Celery


def create_celery_app():
    celery = Celery(
        'facereview',
        broker=None,
        backend=None,
        include=[
            'common.tasks.scheduled_tasks',
        ]
    )

    from common.config.celery_config import CeleryConfig
    celery.config_from_object(CeleryConfig)

    return celery


def init_celery_app(app, celery=None):
    celery = celery or celery_app
    if getattr(celery, '_facereview_flask_app', None) is app:
        return celery

    celery.conf.update(app.config)
    base_task = celery.Task

    class FlaskContextTask(base_task):
        abstract = True

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return super().__call__(*args, **kwargs)

    celery.Task = FlaskContextTask
    celery._facereview_flask_app = app
    return celery


def create_worker_celery(app_factory, config_name, celery=None):
    app = app_factory(
        config_name,
        preload_emotion_model=False,
    )
    return init_celery_app(app, celery)


celery_app = create_celery_app()
