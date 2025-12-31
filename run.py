import os
from dotenv import load_dotenv
from app import create_app, socketio

# .env 파일 로드
load_dotenv()

config_name = os.getenv('FLASK_ENV', 'development')

app = create_app(config_name)

if __name__ == '__main__':
    # 개발 환경에서는 debug=True, socketio 사용
    # 프로덕션 환경에서는 WSGI 서버(gunicorn 등) 사용 권장
    # HTTPS는 Cloudflare에서 처리하므로 HTTP로 실행

    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=(config_name == 'development')
    )
