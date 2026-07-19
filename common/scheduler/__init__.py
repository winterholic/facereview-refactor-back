from flask import Flask
from common.extensions import scheduler


def init_scheduler(app: Flask):
    app.config['SCHEDULER_API_ENABLED'] = True
    app.config['SCHEDULER_TIMEZONE'] = 'Asia/Seoul'

    scheduler.init_app(app)

    from common.scheduler.tasks import register_scheduled_tasks
    register_scheduled_tasks()

    if not scheduler.running:
        scheduler.start()


__all__ = ['init_scheduler']
