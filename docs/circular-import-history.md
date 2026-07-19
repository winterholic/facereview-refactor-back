---
title: "SocketIO Circular Import History"
description: "레거시 단일 파일 구조의 순환 참조 원인과 현재 Application Factory 해결 방식"
document_type: "architecture-history"
status: "historical-with-current-solution"
version: "2.1"
created: "2025-12-20"
updated: "2026-07-19"
source_of_truth:
  - "common/extensions.py"
  - "app/__init__.py"
  - "app/sockets/video_watching_socket.py"
tags: ["python", "flask", "socketio", "circular-import"]
---

# SocketIO 순환 참조 발생 배경

레거시 `origin-codes/run.py`는 SocketIO 초기화와 이벤트 핸들러를 한 파일에 배치해 상호 import를 피했다. 이 문서는 당시 문제가 생긴 이유와 현재 구조가 이를 해결하는 방식을 기록한다.

## 실패하기 쉬운 구조

```python
# run.py
from socket_handlers import register_handlers

app = Flask(__name__)
socketio = SocketIO(app)
register_handlers(socketio)

# socket_handlers.py
from run import socketio
```

의존성 체인은 다음처럼 순환한다.

```text
run.py
  -> socket_handlers.py import
       -> 아직 초기화 중인 run.py의 socketio import
            -> 부분 초기화 모듈 접근 오류
```

문제의 본질은 파일 분리가 아니라 애플리케이션 진입점에서 만들어지는 객체를 하위 모듈이 다시 진입점으로 import한 것이다.

## 현재 해결 구조

### 1. 확장 객체를 독립 모듈에 생성

`common/extensions.py`는 Flask 앱을 import하지 않고 확장 객체만 만든다.

```python
db = SQLAlchemy()
socketio = SocketIO(cors_allowed_origins="*")
api = Api()
```

### 2. Application Factory에서 앱과 연결

`app/__init__.py:create_app`이 앱을 만든 뒤 확장 객체를 초기화한다.

```python
app = Flask(__name__)
db.init_app(app)
socketio.init_app(app)
api.init_app(app)
```

### 3. 초기화 후 이벤트 모듈 import

같은 factory의 마지막 단계에서 `app.sockets.video_watching_socket`을 import한다. 이벤트 모듈은 진입점이나 앱 객체가 아니라 `common.extensions.socketio`만 참조한다.

```python
# app/__init__.py
from app.sockets import video_watching_socket

# app/sockets/video_watching_socket.py
from common.extensions import socketio

@socketio.on('watch_frame')
def handle_watch_frame(message):
    ...
```

의존성은 다음과 같이 단방향이다.

```text
common.extensions
       ^
       |
app factory -> socket handlers
```

## Blueprint가 같은 문제를 피하는 이유

라우트 모듈은 Blueprint만 정의하고 Flask 앱을 import하지 않는다. Application Factory가 라우트 Blueprint를 import해 등록하므로 의존성이 `app factory -> routes` 한 방향으로 유지된다.

## 유지 규칙

- `run.py` 또는 `create_app`이 있는 모듈에서 확장 객체를 가져오지 않는다.
- 공유 확장 객체는 `common.extensions`에서만 import한다.
- 라우트와 소켓 핸들러 등록은 `create_app`의 확장 초기화 이후 수행한다.
- import 순서에 의존하는 새 전역 초기화 로직을 핸들러 모듈에 추가하지 않는다.
