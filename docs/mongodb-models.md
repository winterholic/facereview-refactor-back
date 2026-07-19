---
title: "FaceReview MongoDB Models"
description: "현재 운영 코드가 사용하는 MongoDB 컬렉션과 핵심 필드"
document_type: "database-reference"
status: "active"
version: "2.4"
created: "2025-12-27"
updated: "2026-07-19"
source_of_truth:
  - "app/models/mongodb/video_distribution.py"
  - "app/models/mongodb/youtube_watching_data.py"
  - "app/models/mongodb/video_timeline_emotion_count.py"
  - "app/sockets/video_watching_socket.py"
tags: ["mongodb", "schema", "emotion", "timeline"]
---

# MongoDB 전용 컬렉션

MongoDB는 감정 타임라인과 집계처럼 크기와 구조가 유동적인 데이터를 저장한다. schema-less이므로 과거 문서에는 아래 신규 필드가 없거나 레거시 값 형식이 남아 있을 수 있다.

## 1. `video_distribution`

영상별 실시간 감정 분포와 추천용 가중 점수를 저장한다.

```javascript
{
  "video_id": "uuid",
  "category": "comedy",
  "duration": 180,
  "total_frames": 540,
  "emotion_counts": {
    "neutral": 120,
    "happy": 300,
    "surprise": 80,
    "sad": 25,
    "angry": 15
  },
  "emotion_averages": {
    "neutral": 0.2222,
    "happy": 0.5556,
    "surprise": 0.1481,
    "sad": 0.0463,
    "angry": 0.0278
  },
  "recommendation_scores": {
    "neutral": 0.0444,
    "happy": 2.778,
    "surprise": 0.2962,
    "sad": 0.0139,
    "angry": 0.0139
  },
  "dominant_emotion": "happy",
  "average_completion_rate": 1.0,
  "created_at": ISODate("2026-07-19T00:00:00Z"),
  "updated_at": ISODate("2026-07-19T00:03:00Z")
}
```

- `dominant_emotion`은 raw `emotion_averages` 최댓값이며 30프레임 미만이면 `null`이다.
- `recommendation_scores`는 카테고리 가중치를 적용한 동일 감정 내 정렬용 점수다.
- 현재 프론트와 서버의 샘플링 계약은 0.5초마다 1회, 즉 초당 2프레임이다. 타임라인 키가 centisecond 단위여도 수집 주기가 0.1초라는 의미는 아니다.
- `video_distribution.average_completion_rate`와 `WatchingDataService`의 세션 완료율은 모두 `duration * 2`를 완주 프레임 수로 사용한다.

## 2. `youtube_watching_data`

사용자별 한 번의 영상 시청 세션과 감정 타임라인을 저장한다.

```javascript
{
  "user_id": "uuid",
  "video_id": "uuid",
  "video_view_log_id": "uuid",
  "created_at": ISODate("2026-07-19T00:00:00Z"),
  "updated_at": ISODate("2026-07-19T00:03:00Z"),
  "finalized_at": ISODate("2026-07-19T00:03:00Z"),
  "duration": 180,
  "frame_count": 1800,
  "completion_rate": 1.0,
  "dominant_emotion": "happy",
  "emotion_sum": {
    "neutral": 36000.0,
    "happy": 108000.0,
    "surprise": 18000.0,
    "sad": 9000.0,
    "angry": 9000.0
  },
  "emotion_percentages": {
    "neutral": 0.2,
    "happy": 0.6,
    "surprise": 0.1,
    "sad": 0.05,
    "angry": 0.05
  },
  "emotion_seconds": {
    "neutral": 30,
    "happy": 120,
    "surprise": 20,
    "sad": 5,
    "angry": 5
  },
  "most_emotion_timeline": {
    "0": "neutral",
    "10": "happy"
  },
  "emotion_score_timeline": {
    "0": [90.0, 10.0, 0.0, 0.0, 0.0],
    "10": [20.0, 70.0, 5.0, 3.0, 2.0]
  },
  "client_info": {
    "ip_address": null,
    "user_agent": null,
    "device": {"os": null, "browser": null, "is_mobile": false}
  }
}
```

- 타임라인 키는 `int(youtube_running_time * 100)`인 centisecond 문자열이다.
- 현재 `watch_frame`은 타임라인, `frame_count`, `emotion_sum`, `emotion_percentages`, `dominant_emotion`을 프레임마다 갱신한다.
- `emotion_seconds`와 `finalized_at`은 과거 `end_watching` 종료 경로와 생성 데이터에 사용된 호환 필드다. 현재 프론트는 종료 이벤트를 보내지 않으므로 일반 실시간 세션에서는 자동으로 기록되지 않는다.
- 인덱스: `(user_id, created_at desc)`, `(user_id, finalized_at, video_view_log_id)`, `(video_id, created_at desc)`, unique `video_view_log_id`.

## 3. `video_timeline_emotion_count`

영상의 각 centisecond 위치에서 사용자들이 느낀 감정 횟수를 누적한다.

```javascript
{
  "video_id": "uuid",
  "created_at": ISODate("2026-07-19T00:00:00Z"),
  "emotion_labels": ["neutral", "happy", "surprise", "sad", "angry"],
  "counts": {
    "0": {"neutral": 5, "happy": 2},
    "10": {"neutral": 4, "happy": 3, "surprise": 1}
  }
}
```

현재 쓰기 형식은 감정명별 객체다. `VideoTimelineEmotionCount`의 읽기 로직은 과거 배열 형식도 호환한다. `video_id`에는 unique 인덱스가 있다.

## 제거되거나 통합된 레거시 컬렉션

- `video_distribution_history`: 현재 모델과 쓰기 경로가 없어 사용하지 않는다.
- `youtube_watching_timeline`, `youtube_watching_timeline_data`: `youtube_watching_data`로 통합됐다.
- `timeline_emotion_num`, `timeline_emotion_per`, `timeline_emotion_most`: `video_timeline_emotion_count`로 통합됐다.
