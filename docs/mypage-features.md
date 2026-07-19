---
title: "FaceReview My Page Features"
description: "마이페이지 감정 분석 API와 집계 방식의 현재 동작"
document_type: "feature-reference"
status: "active"
version: "3.1"
created: "2026-02-20"
updated: "2026-07-19"
source_of_truth:
  - "app/routes/mypage.py"
  - "app/services/mypage_service.py"
  - "app/schemas/mypage.py"
tags: ["mypage", "emotion", "analytics", "api"]
---

# FaceReview 마이페이지 기능 명세

> 여섯 개 분석 기능이 모두 구현돼 있다. 응답 구조가 충돌하면 `source_of_truth`의 코드가 우선한다.

---

## 탭 구성

마이페이지는 6개의 탭으로 구성된다.

| 탭 순서 | 탭명 | 기능 ID |
|--------|------|---------|
| 1 | 최근 시청 | 1.1 |
| 2 | 감정 요약 | 1.2 |
| 3 | 하이라이트 | 1.3 |
| 4 | 감정 캘린더 | 2.1 |
| 5 | 베스트 모먼트 | 2.2 |
| 6 | 감정 DNA | 2.3 |

**디자인 방향**: 각 탭은 카드 기반의 레이아웃으로, 감정 데이터 시각화가 중심이 되도록 구성. 서비스 톤에 맞는 감정 색상 팔레트(happy → warm, sad → cool 등)를 탭 전반에 일관되게 적용 권장.

---

## 1. 핵심 기능

### 1.1 최근 시청 영상

사용자가 최근 시청한 영상 목록을 감정 데이터와 함께 조회한다.

**API**: `GET /api/v2/mypage/videos/recent`

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| emotion | string | X | all | neutral / happy / surprise / sad / angry / all |
| page | int | X | 1 | 페이지 번호 |
| size | int | X | 10 | 페이지당 항목 수 |

**응답 데이터**
```json
{
  "videos": [
    {
      "video_id": "uuid",
      "youtube_url": "https://www.youtube.com/watch?v=xxxxx",
      "title": "영상 제목",
      "dominant_emotion": "happy",
      "dominant_emotion_per": 45.5,
      "watched_at": "2026-02-10T15:30:00",
      "timeline_data": [
        {
          "id": "happy",
          "data": [{"x": 1, "y": 30.5}, {"x": 2, "y": 45.2}]
        }
      ]
    }
  ],
  "total": 100,
  "page": 1,
  "size": 10,
  "has_next": true
}
```

---

### 1.2 감정 요약

전체 시청 기록 기반으로 5가지 감정의 누적 시간과 비율을 제공한다.

최초 조회는 기존 MongoDB 타임라인을 한 번 집계하고, 이후에는 MariaDB `user_emotion_summary`의 체크포인트와 `lock_version`을 사용해 새로 종료된 세션만 낙관적으로 합산한다. 신규 세션은 종료 시 MongoDB에 `emotion_seconds`와 `finalized_at`을 저장한다.

**API**: `GET /api/v2/mypage/emotion/summary`

**응답 데이터**
```json
{
  "emotion_percentages": {
    "neutral": 35.2,
    "happy": 28.5,
    "surprise": 15.3,
    "sad": 12.0,
    "angry": 9.0
  },
  "emotion_seconds": {
    "neutral": 12672,
    "happy": 10260,
    "surprise": 5508,
    "sad": 4320,
    "angry": 3240
  }
}
```

**디자인 방향**: 도넛 차트 또는 레이더 차트로 감정 비율 시각화.

---

### 1.3 하이라이트

시청 기록 중 가장 인상적인 데이터를 요약하여 제공한다.

**API**: `GET /api/v2/mypage/highlight`

**응답 데이터**
```json
{
  "emotion_videos": [
    {
      "emotion": "happy",
      "video_id": "uuid",
      "youtube_url": "https://www.youtube.com/watch?v=xxxxx",
      "title": "가장 행복했던 영상",
      "emotion_percentage": 78.5
    }
  ],
  "category_emotions": [
    {
      "category": "comedy",
      "dominant_emotion": "happy",
      "percentage": 55.3
    }
  ],
  "most_watched_category": "comedy",
  "most_felt_emotion": "happy"
}
```

**핵심 로직**
1. **감정별 대표 영상**: 각 감정에서 가장 높은 비율을 기록한 영상
2. **카테고리별 주요 감정**: 각 카테고리에서 가장 많이 느낀 감정
3. **가장 많이 시청한 카테고리**: 시청 횟수 기준 Top 1
4. **가장 많이 느낀 감정**: 전체 누적 기준

---

## 2. 추가 분석 기능

### 2.1 감정 캘린더

일별 감정을 히트맵 형태로 시각화한다. GitHub 잔디와 유사한 UX.

**API**: `GET /api/v2/mypage/emotion/calendar`

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| year | int | X | 현재 연도 | 조회 연도 |
| month | int | X | null | 특정 월 조회 (null이면 연도 전체) |

**응답 데이터**
```json
{
  "year": 2026,
  "data": [
    {
      "date": "2026-02-01",
      "dominant_emotion": "happy",
      "intensity": 0.85,
      "watch_count": 5,
      "total_watch_time": 3600
    }
  ]
}
```

**디자인 방향**: 날짜별 셀에 감정 색상을 입히고, 시청량에 따라 채도/명도를 조절하는 히트맵 방식. 날짜 클릭 시 해당 날짜의 시청 목록을 모달 또는 사이드 패널로 노출.

**현재 구현**: MongoDB `youtube_watching_data.created_at`, `dominant_emotion`, `emotion_percentages`를 요청 시 집계한다. `total_watch_time`은 현재 타임라인을 초당 2프레임으로 환산하지만 수집 경로는 초당 10프레임을 사용하므로 보정 필요.

---

### 2.2 베스트 모먼트

영상 시청 중 감정이 피크(80% 이상)였던 순간을 자동 수집하여 제공한다.

**API**
```
GET /api/v2/mypage/moments
```

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| emotion | string | X | all | 감정 필터 |
| page | int | X | 1 | 페이지 번호 |
| size | int | X | 10 | 페이지당 항목 수 |

**응답 데이터**
```json
{
  "moments": [
    {
      "video_id": "uuid",
      "video_title": "코미디 영상",
      "youtube_url": "https://youtube.com/watch?v=xxx",
      "timestamp_seconds": 125.5,
      "emotion": "happy",
      "emotion_percentage": 92.3,
      "thumbnail_url": "https://img.youtube.com/vi/xxx/hqdefault.jpg",
      "watched_at": "2026-02-10T15:30:00"
    }
  ],
  "total": 45,
  "has_next": true
}
```

**핵심 로직**
- 시청 중 특정 감정이 80% 이상 피크 구간을 자동 감지하여 저장
- 타임스탬프 기록 → 프론트에서 YouTube embed에 `start=125` 파라미터로 해당 구간 바로 재생

**현재 구현**: 별도 moments 테이블을 만들지 않는다. 최근 시청 문서 최대 200개의 `emotion_score_timeline`에서 30초 구간별 최고 80% 이상 프레임을 계산하고 페이지네이션한다.

**디자인 방향**: 썸네일 + 감정 뱃지 + 타임스탬프로 구성된 카드 그리드. 감정 탭으로 필터링 가능.

---

### 2.3 감정 DNA 프로필

전체 감정 데이터를 분석해 개인화된 시청 성향 유형을 제공한다.

**API**: `GET /api/v2/mypage/emotion-dna`

**응답 데이터**
```json
{
  "dna_type": "JOYFUL_EXPLORER",
  "dna_title": "유쾌한 탐험가",
  "dna_description": "새로운 장르를 두려워하지 않고, 어디서든 웃음을 찾아내는 당신!",
  "traits": [
    {"trait": "웃음 포인트가 낮음", "score": 85},
    {"trait": "장르 탐험가", "score": 72},
    {"trait": "몰입형 시청자", "score": 88}
  ],
  "emotion_radar": {
    "happy": 85,
    "surprise": 65,
    "neutral": 45,
    "sad": 30,
    "angry": 15
  },
  "fun_facts": [
    "당신은 평균보다 32% 더 자주 웃어요",
    "드라마를 볼 때도 happy가 가장 높은 희귀한 타입!"
  ],
  "generated_at": "2026-02-20T00:00:00",
  "based_on_videos": 156
}
```

**DNA 유형 (8가지)**

| 유형 코드 | 한글명 | 주요 특징 |
|---------|-------|---------|
| JOYFUL_EXPLORER | 유쾌한 탐험가 | happy↑, 다양한 장르 |
| EMOTIONAL_DIVER | 감성 다이버 | sad/happy 모두 높음, 몰입도↑ |
| THRILL_SEEKER | 스릴 추구자 | surprise↑ |
| CALM_OBSERVER | 차분한 관찰자 | neutral↑, 정보성 콘텐츠 |
| MOOD_SURFER | 무드 서퍼 | 감정 변화폭 큼 |
| COMFORT_LOVER | 안정 추구자 | 익숙한 장르 반복 |
| NIGHT_OWL | 밤의 시청자 | 야간 시청 비중↑ |
| BINGE_MASTER | 정주행 마스터 | 완주율↑ |

**현재 DB 스키마 (MariaDB)**
```sql
CREATE TABLE user_emotion_dna (
    user_id VARCHAR(36) PRIMARY KEY,
    dna_type VARCHAR(50) NOT NULL,
    dna_data JSON NOT NULL,
    based_on_videos INT NOT NULL,
    generated_at DATETIME NOT NULL,
    expires_at DATETIME NOT NULL
);
```

**캐싱 전략**: 매번 전체 데이터를 계산하면 비용이 크므로, `user_emotion_dna` 테이블에 결과를 캐싱. 영상 시청 횟수가 이전 계산 대비 5개 이상 증가했거나 `expires_at`이 지난 경우 재계산.

**디자인 방향**: MBTI 결과 카드처럼 유형명 + 설명 + 레이더 차트 조합. 공유하고 싶은 카드 형태로 구성하면 바이럴 효과 기대 가능.
