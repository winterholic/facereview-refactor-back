# facereview 프로젝트 가이드

YouTube 영상 시청 중 웹캠으로 감정을 실시간 분석하고, 감정 기반 영상 추천을 제공하는 Flask 백엔드 서비스.

## 기술 스택

- **웹 프레임워크**: Flask + Flask-Smorest (OpenAPI/Swagger 자동 생성) + Flask-SocketIO
- **RDB**: MySQL (SQLAlchemy ORM)
- **NoSQL**: MongoDB (pymongo, 시청 데이터·감정 분포)
- **캐시/메시지큐**: Redis (세션·블랙리스트·메트릭)
- **비동기 작업**: Celery (Kafka 소비 처리)
- **스케줄러**: APScheduler (YouTube 데이터 수집)
- **ML**: TensorFlow/Keras (model.h5 — 얼굴 감정 분류)
- **인프라**: Docker, Gunicorn, Cloudflare (HTTPS 처리)

## 디렉토리 구조

```
app/
  models/          # SQLAlchemy 모델 + MongoDB 도큐먼트 클래스
    mongodb/       # YoutubeWatchingData, VideoDistribution 등
  routes/          # Flask-Smorest Blueprint (엔드포인트 정의)
  schemas/         # marshmallow 직렬화/역직렬화 스키마
  services/        # 비즈니스 로직 (정적 메서드 패턴)
  dto/             # 서비스 계층 반환용 DTO 클래스
  sockets/         # Flask-SocketIO 이벤트 핸들러

common/
  config/          # Flask Config 클래스 (development/production)
  decorator/       # auth_decorators, db_decorators (@transactional 등)
  enum/            # APIError, GenreEnum 등
  exception/       # BusinessError
  extensions.py    # db, mongo_db, redis_client, scheduler, socketio 초기화
  scheduler/
    jobs/          # YoutubeTrendingJob, YoutubeCategoryFillJob
    tasks.py       # APScheduler 작업 등록
  utils/           # 토큰 디코딩, 로깅 유틸
  ml/              # 감정 분류 모델 로더
  saga/            # 분산 트랜잭션 Saga 패턴 구현
```

## 핵심 아키텍처 패턴

### Route → Service → DTO 흐름
- `routes/` Blueprint에서 요청 수신 → `services/` 정적 메서드 호출 → DTO 딕셔너리 반환
- `@login_required` → `@admin_required` → `@blueprint.arguments` → `@blueprint.response` 데코레이터 순서 유지
- `@transactional`: MySQL 커밋/롤백 자동 처리. 쓰기 작업에 사용
- `@transactional_readonly`: 읽기 전용 쿼리에 사용

### 에러 처리
- 비즈니스 예외는 `BusinessError(APIError.XXX)` 사용 (HTTPException 자동 변환)
- `APIError` enum에 에러 코드/HTTP 상태/메시지 정의

### MongoDB 접근
- 각 컬렉션에 Repository 클래스 (find, insert, upsert 메서드)
- `common/extensions.py`의 `mongo_db` 객체를 Repository 생성자에 전달

### 소켓 이벤트 (시청 중 실시간)
- `watch_frame`: 클라이언트에서 프레임 감정 데이터 수신 → Redis 캐시에 누적
- `stop_watching`: 캐시 → MongoDB 영구 저장 트리거
- 타임라인 키는 **centisecond 단위** (`초 × 100`): `20.29초 → "2029"`

## 코드 컨벤션

### 주석
- **주석 최소화**: 코드로 의도가 명확하면 주석 없음
- **비자명한 로직만** `#NOTE:` 사용 (공백 없이, 콜론 포함)
- docstring 사용하지 않음

### 로그
- 모든 로그 메시지는 **한국어**
- `get_logger('모듈명')` 으로 로거 생성

### 스키마 (marshmallow)
- 요청 파라미터: `XXXRequestSchema`, 응답: `XXXResponseSchema`
- query string: `@blueprint.arguments(Schema, location='query')`
- body: `@blueprint.arguments(Schema)` (location 생략)
- 필드 범위 제한: `validate.Range(min=..., max=...)`

## 주요 데이터 모델

### GenreEnum (16개 카테고리)
`drama, eating, travel, cook, show, information, game, sports, music, animal, beauty, comedy, horror, exercise, vlog, etc`

### YoutubeWatchingData (MongoDB)
- `emotion_score_timeline`: `{centisecond_str: [neutral, happy, surprise, sad, angry]}`
- `most_emotion_timeline`: `{centisecond_str: emotion_name}`
- `emotion_percentages`: 세션 전체 감정 비율 (0~1)
- `completion_rate`: 시청 완료율 (0~1)

### VideoDistribution (MongoDB)
- `emotion_averages`: 전체 시청자 평균 감정
- `recommendation_scores`: 추천 가중치 (감정별 배율 적용)
- `dominant_emotion`: 대표 감정

## YouTube 스케줄러

| Job | 주기 | Quota 소비 |
|-----|------|-----------|
| YoutubeTrendingJob | 매일 06:00 | ~4 units/run |
| YoutubeCategoryFillJob | 화·금 03:00 | 최대 1,200 units/run |

- 일일 YouTube API 무료 quota: 10,000 units
- `search.list` = 100 quota/call, `videos.list` = 1 quota/call

## 개발 실행

```bash
python run.py                    # Flask 개발 서버 (SocketIO 포함)
python celery_worker.py          # Celery 워커
python run_kafka_consumer.py     # Kafka 소비자
```
