"""
Routes package
Flask Blueprint들을 관리하는 패키지
"""

from app.routes.auth import auth_blueprint
from app.routes.home import home_blueprint
from app.routes.mypage import mypage_blueprint
from app.routes.watch import watch_blueprint
from app.routes.admin import admin_blueprint
from app.routes.base import base_blueprint

__all__ = [
    'auth_blueprint',
    'home_blueprint',
    'mypage_blueprint',
    'watch_blueprint',
    'admin_blueprint',
    'base_blueprint'
]
