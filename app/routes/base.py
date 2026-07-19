from datetime import datetime

from flask_smorest import Blueprint
from common.decorator.auth_decorators import public_route

base_blueprint = Blueprint(
    'base',
    __name__,
    url_prefix='/',
    description='기본 테스트 엔드포인트'
)

@base_blueprint.route('', methods = ['GET'])
@public_route
def base_endpoint():
    return {
        "status": "ok",
        "service": "facereview",
        "time": datetime.now().isoformat()
    }
