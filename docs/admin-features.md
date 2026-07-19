---
title: "FaceReview Admin Features"
description: "관리자 API와 대시보드 기능의 현재 동작 및 응답 구조"
document_type: "feature-reference"
status: "active"
version: "2.1"
created: "2026-02-20"
updated: "2026-07-19"
source_of_truth:
  - "app/routes/admin.py"
  - "app/services/admin_service.py"
  - "app/schemas/admin.py"
tags: ["admin", "api", "monitoring", "dashboard"]
---

# FaceReview 어드민 기능 명세

> 이 문서는 현재 구현을 설명한다. 엔드포인트·필드가 충돌하면 `source_of_truth`의 코드가 우선한다.

---

## 메뉴 구성

| 메뉴 | 설명 |
|------|------|
| 사용자 관리 | 회원 목록 조회, 비활성화, 권한 변경 |
| 영상 관리 | 추천 영상 등록/삭제, 요청 승인·거절 |
| 시스템 모니터링 | 서버 상태, API 응답 시간, Redis/DB 상태 |
| 댓글 관리 | 댓글 목록 조회 및 삭제 |

**디자인 방향**: 사이드바 네비게이션 + 우측 콘텐츠 영역의 전형적인 어드민 레이아웃. 테이블 중심의 데이터 열람 UI.

---

## 1. 사용자 관리

### 1.1 사용자 목록 조회

**API**: `GET /api/v2/admin/users`

| 파라미터 | 타입 | 설명 |
|---------|------|------|
| page | int | 페이지 번호 |
| size | int | 페이지당 항목 수 |
| keyword | string | 이름/이메일 검색 |
| is_deleted | bool | 탈퇴 회원 포함 여부 |

**응답 데이터**
```json
{
  "users": [
    {
      "user_id": "uuid",
      "email": "user@example.com",
      "name": "홍길동",
      "role": "GENERAL",
      "is_deleted": false,
      "created_at": "2026-01-01T00:00:00"
    }
  ],
  "total": 500,
  "page": 1,
  "size": 20,
  "has_next": true
}
```

### 1.2 사용자 비활성화

**API**: `PATCH /api/v2/admin/users/{user_id}/deactivate`

현재 구현은 `user.is_deleted = 1`로 계정을 비활성화하고 작성 댓글도 soft delete한다. `ADMIN`은 `GENERAL` 사용자만 처리할 수 있고 `SUPER_ADMIN`은 모든 역할을 처리할 수 있다.

### 1.3 권한 변경

**API**: `PATCH /api/v2/admin/users/{user_id}/role`

```json
{ "role": "ADMIN" }
```

---

## 2. 영상 관리

### 2.1 등록된 영상 목록

**API**: `GET /api/v2/admin/videos`

| 파라미터 | 타입 | 설명 |
|---------|------|------|
| page | int | 페이지 번호 |
| size | int | 페이지당 항목 수 |
| category | string | 카테고리 필터 |
| keyword | string | 제목 검색 |

**응답 데이터**
```json
{
  "videos": [
    {
      "video_id": "uuid",
      "title": "영상 제목",
      "youtube_url": "xxxx",
      "category": "comedy",
      "view_count": 1200,
      "like_count": 85,
      "is_deleted": 0,
      "created_at": "2026-01-15T00:00:00"
    }
  ],
  "total": 200,
  "has_next": true
}
```

### 2.2 영상 삭제

**API**: `DELETE /api/v2/admin/videos/{video_id}`

soft delete (`is_deleted = 1`) 처리.

### 2.3 영상 추천 요청 목록

사용자들이 추천한 영상 요청을 조회하고 승인/거절 처리한다.

**API**: `GET /api/v2/admin/video-requests`

| 파라미터 | 타입 | 설명 |
|---------|------|------|
| status | string | PENDING / ACCEPTED / REJECTED |
| page | int | 페이지 번호 |

**응답 데이터**
```json
{
  "requests": [
    {
      "request_id": "uuid",
      "user_id": "uuid",
      "user_name": "홍길동",
      "youtube_url": "https://youtube.com/watch?v=xxx",
      "title": "추천 영상 제목",
      "category": "comedy",
      "status": "PENDING",
      "created_at": "2026-02-10T00:00:00"
    }
  ],
  "total": 30,
  "has_next": false
}
```

### 2.4 영상 요청 승인

**API**: `POST /api/v2/admin/video-requests/{request_id}/approve`

승인 요청 본문으로 제목, 채널명, 길이, 16종 카테고리 중 하나를 받아 `video` 테이블에 등록한다.

### 2.5 영상 요청 거절

**API**: `POST /api/v2/admin/video-requests/{request_id}/reject`

```json
{ "admin_comment": "중복 영상입니다." }
```

---

## 3. 시스템 모니터링

> 현재 구현됨. `app/__init__.py`가 요청 메트릭을 Redis에 기록하고 `AdminService.get_system_status`가 서버 및 연결 상태를 조회한다.

### 3.1 기능 개요

관리자가 서버 상태를 실시간으로 확인할 수 있는 대시보드.

**API**: `GET /api/v2/admin/system/status`

**응답 데이터**
```json
{
  "server": {
    "cpu_usage": 23.4,
    "memory_usage": 61.2,
    "memory_total_mb": 8192,
    "disk_usage": 44.0
  },
  "api": {
    "total_requests_1h": 1240,
    "avg_response_time_ms": 85,
    "error_rate_1h": 0.8
  },
  "connections": {
    "mysql": "ok",
    "redis": "ok",
    "mongodb": "ok"
  },
  "checked_at": "2026-02-20T14:30:00"
}
```

### 3.2 구현 방법

#### 서버 리소스 (CPU / 메모리 / 디스크)
`requirements.txt`에 포함된 `psutil`로 수집한다.

```python
import psutil

cpu = psutil.cpu_percent(interval=1)
mem = psutil.virtual_memory()
disk = psutil.disk_usage('/')
```

별도 에이전트 없이 Flask 서비스에서 직접 호출한다.

#### API 요청 통계 (요청 수, 응답 시간, 에러율)
Flask의 `before_request` / `after_request` 훅에서 Redis에 카운터를 적재한다. 키 TTL은 1시간이다.

```python
# before_request: 요청 시작 시각 기록
g.start_time = time.time()

# after_request: 응답 시간 계산 후 Redis에 저장
elapsed_ms = (time.time() - g.start_time) * 1000
redis_client.incr("facereview:metrics:requests:1h")
redis_client.lpush("facereview:metrics:response_times", elapsed_ms)
redis_client.ltrim("facereview:metrics:response_times", 0, 999)  # 최근 1000건만 유지
```

HTTP 상태 코드가 400 이상이면 `facereview:metrics:errors:1h`를 증가시킨다.

#### DB / Redis / MongoDB 연결 상태
각 클라이언트에 간단한 ping 쿼리로 체크한다.

```python
# MySQL (SQLAlchemy)
db.session.execute(text("SELECT 1"))

# Redis
redis_client.ping()

# MongoDB
mongo_db.command("ping")
```

응답이 오면 `"ok"`, 예외 발생 시 `"error"` 반환.

### 3.3 폴링 방식

프론트에서 30초 간격으로 API를 폴링하는 방식으로 충분하다. SSE(Server-Sent Events)나 WebSocket은 이 수준의 모니터링에서는 오버엔지니어링.

### 3.4 추가 고려사항

- `psutil`은 `requirements.txt`로 설치된다
- Redis 메트릭 키는 만료 시간(`expire`)을 설정해 자동 정리
- 이 API는 어드민 전용이므로 반드시 어드민 권한 체크 데코레이터 적용

---

## 4. 댓글 관리

### 4.1 댓글 목록

**API**: `GET /api/v2/admin/comments`

| 파라미터 | 타입 | 설명 |
|---------|------|------|
| page | int | 페이지 번호 |
| size | int | 페이지당 항목 수 |
| video_id | string | 특정 영상의 댓글만 조회 |
| keyword | string | 댓글 내용 검색 |
| is_deleted | bool | 삭제된 댓글 포함 여부 |

**응답 데이터**
```json
{
  "comments": [
    {
      "comment_id": "uuid",
      "user_id": "uuid",
      "user_name": "홍길동",
      "video_id": "uuid",
      "video_title": "영상 제목",
      "content": "댓글 내용",
      "is_deleted": 0,
      "created_at": "2026-02-15T10:00:00"
    }
  ],
  "total": 300,
  "has_next": true
}
```

### 4.2 댓글 삭제

**API**: `DELETE /api/v2/admin/comments/{comment_id}`

soft delete (`is_deleted = 1`) 처리. 기존 탈퇴 처리 로직과 동일한 방식.

---

## 5. 대시보드 및 운영 보조 API

| API | 권한 | 용도 |
|-----|------|------|
| `GET /api/v2/admin/dashboard/business-stats` | ADMIN 이상 | 가입 추이, WAU, 요청 처리, 콘텐츠 건강도 |
| `GET /api/v2/admin/dashboard/signup-trend` | ADMIN 이상 | 기간별 가입 추이 |
| `POST /api/v2/admin/dummy-data` | SUPER_ADMIN | 테스트용 시청·감정 데이터 생성 |

WAU는 Redis에 15분 캐시한다. 더미 데이터 API는 운영 데이터 변경을 수반하므로 SUPER_ADMIN 전용이다.
