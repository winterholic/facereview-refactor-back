"""
Scheduler 초기화 및 설정
APScheduler를 사용한 백그라운드 작업 스케줄링
"""
from flask import Flask
from common.extensions import scheduler


def init_scheduler(app: Flask):
    """
    스케줄러 초기화 및 앱에 등록
    """
    # APScheduler 설정
    app.config['SCHEDULER_API_ENABLED'] = True
    app.config['SCHEDULER_TIMEZONE'] = 'Asia/Seoul'

    # 스케줄러를 앱에 초기화
    scheduler.init_app(app)

    # 스케줄 작업 등록
    from common.scheduler.tasks import register_scheduled_tasks
    register_scheduled_tasks()

    # 스케줄러 시작
    if not scheduler.running:
        scheduler.start()


__all__ = ['init_scheduler']
