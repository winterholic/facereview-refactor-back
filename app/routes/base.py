from datetime import datetime

from flask_smorest import Blueprint

base_blueprint = Blueprint(
    'base',
    __name__,
    url_prefix='/',
    description='기본 테스트 엔드포인트'
)

@base_blueprint.route('', methods = ['GET'])
def base_endpoint(request):
    return{
        "status": "ok",
        "service": "facereview",
        "time": datetime.now().isoformat()
    }