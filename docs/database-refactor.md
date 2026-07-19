---
title: "FaceReview Database Refactor"
description: "레거시 MongoDB에서 현재 MariaDB·MongoDB 혼합 구조로 이동한 설계 기록"
document_type: "migration-reference"
status: "reference-with-legacy-examples"
version: "2.1"
created: "2025-12-27"
updated: "2026-07-19"
source_of_truth:
  - "app/models/"
  - "app/models/mongodb/"
tags: ["database", "mariadb", "mongodb", "migration"]
---

# 리팩토링 DB 구조와 현재 차이

> 아래 SQL·JSON 블록은 리팩토링 당시 설계 기록이며 그대로 실행하는 DDL이 아니다. 현재 구조는 `source_of_truth`의 모델 코드와 [MongoDB 모델](mongodb-models.md)을 우선한다.

## 2026-07-19 현재 주요 변경점

- `user.role`은 `GENERAL`, `ADMIN`, `SUPER_ADMIN`을 지원하고 이메일 인증 상태를 저장한다.
- 영상 카테고리는 `horror`, `exercise`, `vlog`를 포함한 16종이다.
- `video_request`에는 `category`가 없으며 승인 시 관리자가 카테고리를 전달한다.
- `youtube_watching_data`에는 `frame_count`, `emotion_sum`, `emotion_seconds`, `finalized_at`이 추가됐다. 현재 실시간 경로는 앞의 두 누적 필드만 `watch_frame`에서 갱신한다.
- 도넛 차트 증분 집계를 위해 MariaDB `user_emotion_summary` 테이블을 사용한다. 다만 프론트의 세션 종료 이벤트가 폐기된 뒤 자동 finalization 경로는 아직 대체되지 않아 신규 일반 시청 세션의 증분 반영에는 제한이 있다.
- 미사용 Socket.IO `init_watching`·`end_watching` 이벤트와 `watching_data.save` Celery 작업은 제거됐으며, `watch_frame`이 세션 초기화와 실시간 저장을 단독으로 담당한다.
- `video_timeline_emotion_count.counts`의 현재 값은 감정명별 객체이며, 배열 형식은 읽기 호환만 유지한다.

### 현재 모델 인벤토리

| 저장소 | 현재 모델/컬렉션 |
|--------|------------------|
| MariaDB | `user`, `user_favorite_genre`, `user_point_history`, `video`, `video_view_log`, `video_request`, `video_like`, `video_bookmark`, `comment`, `user_emotion_dna`, `user_emotion_summary` |
| MongoDB | `video_distribution`, `youtube_watching_data`, `video_timeline_emotion_count` |

---

## 1. user (사용자 정보)

### 기존 테이블 내용(mongoDB)
```javascript
{
  _id: ObjectId("..."),
  user_index: 1,                          // INT, 사용자 고유 번호 (자동증가)
  user_email_id: "user@example.com",      // STRING, 이메일 (로그인 ID)
  user_pw: "$2b$12$...",                  // STRING, bcrypt 해시 비밀번호
  user_name: "김철수",                     // STRING, 사용자 이름 (2-10자)
  user_favorite_genre_1: "drama",         // STRING, 선호 장르 1
  user_favorite_genre_2: "game",          // STRING, 선호 장르 2
  user_favorite_genre_3: "sports",        // STRING, 선호 장르 3
  user_create_time: ISODate("2023-11-29T..."), // DATETIME, 생성일시
  user_role: 1,                           // INT, 권한 (1: 일반, 2: 관리자)
  user_point: 0,                          // INT, 포인트 (미사용)
  user_profile: 0,                        // INT, 프로필 사진 번호
  user_tutorial: 0,                       // INT, 튜토리얼 진행 횟수
  user_activate: 7                        // INT, 활성화 상태 (7: 활성, 0: 비활성)
}
```

### 리팩토링 후 테이블 내용(mariaDB)

```sql
CREATE TABLE user (
      user_id             VARCHAR(36) PRIMARY KEY COMMENT '사용자 고유 ID (UUID)',
      email               VARCHAR(255) NOT NULL UNIQUE COMMENT '이메일 (로그인 ID)',
      password            VARCHAR(255) NOT NULL COMMENT '암호화된 비밀번호',
      name                VARCHAR(50) NOT NULL COMMENT '사용자 이름',

    -- 상태 및 권한
      role                ENUM('GENERAL', 'ADMIN') DEFAULT 'GENERAL' COMMENT '사용자 권한',
      profile_image_id    INT DEFAULT 0 COMMENT '프로필 이미지 ID (클라이언트 리소스 매핑용)',
      is_tutorial_done    TINYINT(1) DEFAULT 0 COMMENT '튜토리얼 완료 여부 (0:미완료, 1:완료)',
      is_deleted          TINYINT(1) DEFAULT 0 COMMENT '탈퇴 여부 (0:활성, 1:탈퇴)',

    -- 타임스탬프
      created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '생성일시',
      updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '수정일시 (자동 갱신)'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### 리팩토링 후 추가 테이블(mariaDB)
```sql
CREATE TABLE user_favorite_genre (
     user_favorite_genre_id  VARCHAR(36) PRIMARY KEY COMMENT '선호 장르 ID (UUID)',
     user_id                 VARCHAR(36) NOT NULL COMMENT '사용자 ID (FK)',

    -- ENUM으로 장르 값 제한
     genre    ENUM(
                'drama', 'eating', 'travel', 'cook', 'show',
                'information', 'game', 'sports', 'music', 'animal',
                'beauty', 'comedy', 'horror', 'exercise', 'vlog', 'etc'
            ) COMMENT '선호 장르',

     created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '생성일시',
     updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '수정일시',

    -- 외래키 설정
     CONSTRAINT fk_favorite_genre_user
         FOREIGN KEY (user_id) REFERENCES user (user_id)
             ON DELETE CASCADE ON UPDATE CASCADE,

    -- 중복 방지
     UNIQUE KEY uk_user_genre (user_id, genre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### 리팩토링 후 추가 테이블(mariaDB)
```sql
CREATE TABLE user_point_history (
    user_point_history_id VARCHAR(36) PRIMARY KEY COMMENT '포인트 이력 ID (UUID)',
    user_id               VARCHAR(36) NOT NULL COMMENT '사용자 ID (FK)',
    video_id              VARCHAR(36) NULL COMMENT '관련 영상 ID (FK)',

    amount                INT NOT NULL COMMENT '변동 포인트 (양수:획득, 음수:사용)',
    watch_time            INT DEFAULT 0 COMMENT '인정된 시청 시간(초)',
    description           VARCHAR(255) COMMENT '내역 설명',

    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '생성일시',
    updated_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '수정일시',

    -- 외래키 설정
    CONSTRAINT fk_point_history_user
        FOREIGN KEY (user_id) REFERENCES user (user_id)
            ON DELETE CASCADE ON UPDATE CASCADE,

    CONSTRAINT fk_point_history_video
        FOREIGN KEY (video_id) REFERENCES video (video_id)
            ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

---


## 2. youtube_video (YouTube 영상 정보)

### 기존 테이블 내용(mongoDB)
```javascript
{
  _id: ObjectId("..."),
  youtube_index: 1,                                    // INT, 영상 고유 번호
  youtube_url: "dQw4w9WgXcQ",                         // STRING, YouTube 영상 ID
  youtube_real_url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ", // STRING, 전체 URL
  youtube_title: "Never Gonna Give You Up",            // STRING, 영상 제목
  youtube_channel: "Rick Astley",                      // STRING, 채널명
  youtube_length_hour: 0,                              // INT, 영상 길이 (시)
  youtube_length_minute: 3,                            // INT, 영상 길이 (분)
  youtube_length_second: 33,                           // INT, 영상 길이 (초)
  youtube_category: "show",                            // STRING, 카테고리
  youtube_create_date: ISODate("2023-11-29T..."),     // DATETIME, 등록일시
  youtube_hits: 1523,                                  // INT, 조회수
  youtube_like: 342,                                   // INT, 좋아요 수
  youtube_comment_num: 28,                             // INT, 댓글 수
  youtube_activate: 7                                  // INT, 활성화 (7: 활성, 0: 비활성)
}
```

### 리팩토링 후 테이블 내용(mariaDB)
```sql
CREATE TABLE video (
   video_id            VARCHAR(36) PRIMARY KEY COMMENT '영상 고유 ID (UUID) - MongoDB 연결 키 겸용',

   youtube_url         VARCHAR(50) NOT NULL UNIQUE COMMENT '유튜브 영상 ID (예: dQw4w9WgXcQ)',
   title               VARCHAR(255) NOT NULL COMMENT '영상 제목',
   channel_name        VARCHAR(100) COMMENT '채널명',

    -- 카테고리
   category    ENUM(
                'drama', 'eating', 'travel', 'cook', 'show',
                'information', 'game', 'sports', 'music', 'animal',
                'beauty', 'comedy', 'horror', 'exercise', 'vlog', 'etc'
            ) COMMENT '카테고리',

    -- 시간 정보 (초 단위 통합)
   duration            INT DEFAULT 0 COMMENT '영상 길이(초)',

    -- 조회수
   view_count          BIGINT DEFAULT 0 COMMENT '조회수',

   is_deleted          TINYINT(1) DEFAULT 0 COMMENT '삭제 여부 (0:활성, 1:삭제)',
   created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '등록일시',
   updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '수정일시'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

---

## 3. video_distribution (영상별 감정 분포 통계)

### 기존 테이블 내용(mongoDB)
```javascript
{
  _id: ObjectId("..."),
  youtube_index: 1,                        // INT, 영상 고유 번호 (youtube_video 참조)
  watching_data_num: 156,                  // INT, 해당 영상 시청 데이터 수
  video_achivement_avg: 0.78,              // FLOAT, 평균 시청 완료율 (0.0 ~ 1.0)
  emotion_statistics_avg: {                // OBJECT, 감정 평균 비율
    neutral: 0.45,                         // FLOAT, 무표정 평균 비율
    happy: 0.32,                           // FLOAT, 행복 평균 비율
    surprise: 0.10,                        // FLOAT, 놀람 평균 비율
    sad: 0.08,                             // FLOAT, 슬픔 평균 비율
    angry: 0.05                            // FLOAT, 화남 평균 비율
  },
  emotion_statistics_score: {              // OBJECT, 감정 점수 (추천 알고리즘용)
    neutral: 0.45,                         // neutral * 1
    happy: 1.60,                           // happy * 5
    surprise: 1.00,                        // surprise * 10
    sad: 0.56,                             // sad * 7
    angry: 0.35                            // angry * 7
  },
  most_emotion: "neutral",                 // STRING, 가장 많은 감정
  distribution_activate: 7                 // INT, 활성화 상태
}
```
### 리팩토링 후 테이블 내용(mongoDB)
```javascript
// Collection: video_distribution
{
  "_id": ObjectId("..."),

  // MariaDB의 video 테이블 video_id (UUID)와 매핑
  "video_id": "550e8400-e29b-41d4-a716-446655440000",

  // 평균 시청 완료율 (0.0 ~ 1.0)
  "average_completion_rate": 0.78,

  // 감정 평균 비율 (전체 시청자 평균)
  "emotion_averages": {
    "neutral": 0.45,
    "happy": 0.32,
    "surprise": 0.10,
    "sad": 0.08,
    "angry": 0.05
  },

  // [기획 변경 주의] 추천 알고리즘용 가중치 점수
  // 현재 로직: happy * 5, surprise * 10 등 가중치 적용
  // ※ 기획 변경 시 가중치 계산 식 전체 수정 필요
  "recommendation_scores": {
    "neutral": 0.45,
    "happy": 1.60,
    "surprise": 1.00,
    "sad": 0.56,
    "angry": 0.35
  },

  // 가장 지배적인 감정
  "dominant_emotion": "neutral",

  "created_at": ISODate("2023-12-01T10:00:00Z"),

  // 마지막 통계 업데이트 시간 (중요)
  "updated_at": ISODate("2023-12-20T10:00:00Z")
}
```

### 계획했지만 구현하지 않은 히스토리 컬렉션

`video_distribution_history`는 현재 모델과 쓰기 경로가 없다. 아래 블록은 채택되지 않은 설계 기록이다.

```javascript
// Collection: video_distribution_history
{
    "_id": ObjectId("..."),

        // MariaDB video 테이블의 video_id (UUID)
        "video_id": "550e8400-e29b-41d4-a716-446655440000",

        // 히스토리 기록 시점 (Time Series 기준점)
        "recorded_at": ISODate("2024-01-19T00:00:00Z"),

        // --- 아래부터는 통계 데이터 그대로 저장 (Flat Structure) ---

        "average_completion_rate": 0.75,

        "emotion_averages": {
        "neutral": 0.50,
            "happy": 0.20,
            "surprise": 0.10,
            "sad": 0.10,
            "angry": 0.10
    },

    // [기획 변경 주의] 당시 시점의 알고리즘으로 계산된 점수
    "recommendation_scores": {
        "neutral": 0.50,
            "happy": 1.00,
            "surprise": 1.00,
            "sad": 0.70,
            "angry": 0.70
    },

    "dominant_emotion": "neutral"
}
```

---

## 4. youtube_watching_data (사용자 시청 데이터)

### 기존 테이블 내용(mongoDB)
```javascript
{
  _id: ObjectId("..."),
  watching_data_index: 1,                  // INT, 시청 데이터 고유 번호
  user_index: 123,                         // INT, 사용자 번호 (user 참조)
  youtube_index: 45,                       // INT, 영상 번호 (youtube_video 참조)
  data_create_time: ISODate("2023-12-01T..."), // DATETIME, 생성일시
  watching_achivement_per: 0.85,           // FLOAT, 시청 완료율 (0.0 ~ 1.0)
  emotion_statistics_per: {                // OBJECT, 감정 비율
    neutral: 0.50,
    happy: 0.30,
    surprise: 0.10,
    sad: 0.06,
    angry: 0.04
  },
  most_emotion: "neutral",                 // STRING, 가장 많은 감정
  watching_data_activate: 7                // INT, 활성화 상태
}
```

### 리팩토링 후 테이블 내용(mongoDB)
```javascript
// Collection: youtube_watching_data
{
    "_id": ObjectId("..."),

    // 1. 매핑 정보 (RDB와 연결 - UUID)
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "video_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
    "video_view_log_id": "b1e23906-5808-43d6-8b30-2c2c6153365c",

    // 2. 메타 데이터
    "created_at": ISODate("2023-12-01T10:00:00Z"),
    "completion_rate": 0.85,     // 시청 완료율
    "dominant_emotion": "happy", // 영상 전체의 대표 감정

    // 3. 감정 분석 요약 (JSON Object)
    "emotion_percentages": {
    "neutral": 0.50,
        "happy": 0.30,
        "surprise": 0.10,
        "sad": 0.06,
        "angry": 0.04
    },

    // 4. 타임라인 (0.1초 단위, Key-Value 구조)
    // 기존 "00:00:00.1" : 방식은 파싱하는데에도 시간을 많이잡아먹는 구조임
    // Key: 밀리초(ms) 단위의 문자열 (프론트에서 /1000 하면 초 단위 변환 쉬움)
    // Value: 가장 점수가 높았던 감정 (String)
    // 기존 youtube_watching_timeline 테이블과 youtube_watching_timeline_data테이블을 합침
    // 어차피 트렌젝션 처리도 까다롭고 같은 테이블에 있어도 되는 데이터임
    "most_emotion_timeline": {
        "0": "neutral",        // 0초
        "100": "neutral",      // 0.1초
        "200": "happy",        // 0.2초
        "300": "happy",        // 0.3초
        // ...
        "1500": "surprise",    // 1.5초
        "1600": "surprise",    // 1.6초
        // ...
        "60500": "neutral"     // 60.5초 (1분 0.5초)
    },
    "emotion_score_timeline": {
        // 순서: [neutral, happy, surprise, sad, angry]
        "0": [0.9, 0.1, 0, 0, 0],
        "100": [0.8, 0.2, 0, 0, 0],
        "200": [0.5, 0.5, 0, 0, 0],
        // ...
        "1500": [0.1, 0.1, 0.8, 0, 0]
    },

    // [추가] 클라이언트 환경 정보
    "client_info": {
        "ip_address": "192.168.1.100",  // (개인정보 이슈 시 마스킹 처리 고려: 192.168.xxx.xxx)
        "user_agent": "Mozilla/5.0...", // UA string 원문
        "device": {                     // UA 파싱해서 넣거나 프론트에서 보내줌
            "os": "Windows 10",
                "browser": "Chrome 120",
                "is_mobile": false
        }
    }
}
```


---

## 5. youtube_watching_timeline (시청 타임라인 - 초단위 감정)

### 기존 테이블 내용(mongoDB)
```javascript
{
  _id: ObjectId("..."),
  watching_data_index: 1,                  // INT, 시청 데이터 번호 (youtube_watching_data 참조)
  "0:00:01": "neutral",                    // STRING, 1초 시점의 감정
  "0:00:02": "happy",                      // STRING, 2초 시점의 감정
  "0:00:03": "neutral",                    // STRING, 3초 시점의 감정
  // ... 영상 길이만큼 계속
  "0:03:33": "neutral"                     // STRING, 마지막 초의 감정
}
```
### 리팩토링 후 테이블 삭제하고 youtube_watching_data테이블에 데이터 합침
---

## 6. youtube_watching_timeline_data (타임라인 데이터 - 감정 비율)

### 기존 테이블 내용(mongoDB)
```javascript
{
  _id: ObjectId("..."),
  watching_data_index: 1,
  watching_timeline_activate: 7,
  "0:00:01": {                             // 1초 시점
    happy: 0.05,
    neutral: 0.80,
    angry: 0.02,
    sad: 0.08,
    surprise: 0.05
  },
  "0:00:02": {                             // 2초 시점
    happy: 0.15,
    neutral: 0.70,
    angry: 0.03,
    sad: 0.07,
    surprise: 0.05
  },
  // ... 계속
}
```
### 리팩토링 후 테이블 삭제하고 youtube_watching_data테이블에 데이터 합침
---

## 7. timeline_emotion_num (타임라인별 감정 개수)

### 기존 테이블 내용(mongoDB)
```javascript
{
  _id: ObjectId("..."),
  youtube_index: 1,
  timeline_emotion_num_activate: 7,
  "0:00:01": {                             // 1초 시점
    happy: 5,                              // 5명이 happy 감정
    neutral: 20,                           // 20명이 neutral
    angry: 1,
    sad: 3,
    surprise: 2
  },
  // ... 계속
}
```

### 리팩토링 후 테이블 내용(mongoDB)
```javascript
// Collection: video_timeline_emotion_count
{
  "_id": ObjectId("..."),

  // 1. 매핑 정보 (RDB video 테이블의 video_id)
  "video_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",

  "created_at": ISODate("2023-12-01T10:00:00Z"),

  // 2. 기준 정보 (배열의 인덱스가 어떤 감정인지 정의)
  // 이게 있어야 [5, 20, 1, 3, 2]가 무엇을 의미하는지 알 수 있음
  // MongoDB의 $inc 연산자 활용을 위해서 추가 , $inc 연산은 원자성을 지키는 방식으로 처리
  "emotion_labels": ["neutral", "happy", "surprise", "sad", "angry"],

  // 3. 타임라인 카운트 (Sparse Data, ms 단위 Key)
  // Value: emotion_labels 순서에 맞는 각 감정의 '사람 수' (Integer)
  "counts": {
    "0": [5, 2, 0, 0, 0],       // 0초: neutral 5명, happy 2명...
    "100": [5, 3, 0, 0, 0],     // 0.1초: neutral 5명, happy 3명...

    // ... 중간에 아무도 감정을 느끼지 않은(데이터가 없는) 구간은 저장 안 함 ...

    "1500": [10, 50, 5, 2, 1]   // 1.5초: happy(2번째)가 50명으로 급증!
  }
}
```

---

## 8. timeline_emotion_per (타임라인별 감정 비율)

### 기존 테이블 내용(mongoDB)
```javascript
{
  _id: ObjectId("..."),
  youtube_index: 1,
  timeline_emotion_per_activate: 7,
  "0:00:01": {                             // 1초 시점 전체 사용자 평균
    happy: 0.16,                           // 16%가 happy
    neutral: 0.65,                         // 65%가 neutral
    angry: 0.03,
    sad: 0.10,
    surprise: 0.06
  },
  // ... 계속
}
```

### 현재 상태

별도 컬렉션은 제거됐고 `video_timeline_emotion_count`에서 비율을 계산한다.

---

## 9. timeline_emotion_most (타임라인별 주요 감정)
### 기존 테이블 내용(mongoDB)
```javascript
{
  _id: ObjectId("..."),
  youtube_index: 1,
  timeline_emotion_most_activate: 7,
  "0:00:01": "neutral",                    // 1초 시점 주요 감정
  "0:00:02": "happy",
  "0:00:03": "neutral",
  // ... 계속
}
```

### 현재 상태

별도 컬렉션은 제거됐고 `video_timeline_emotion_count`의 감정별 횟수에서 대표 감정을 계산한다.
---

## 10. youtube_inquiry (영상 조회 기록)

### 기존 테이블 내용(mongoDB)
```javascript
{
  _id: ObjectId("..."),
  inquiry_index: 1,                        // INT, 조회 기록 고유 번호
  youtube_index: 45,                       // INT, 영상 번호
  user_id: "user@example.com",             // STRING, 사용자 이메일 (로그인 유저)
  user_token: "temp_token_xyz",            // STRING, 임시 토큰 (비로그인 유저)
  inquiry_activate: 7                      // INT, 활성화 상태
}
```

### 리팩토링 후 테이블 내용(mariaDB)
```sql
CREATE TABLE video_view_log (
    video_view_log_id   VARCHAR(36) PRIMARY KEY COMMENT '시청 기록 ID (UUID)',

    video_id            VARCHAR(36) NOT NULL COMMENT '영상 ID (FK)',
    user_id             VARCHAR(36) NULL COMMENT '사용자 ID (FK, 비로그인 시 NULL)',
    guest_token         VARCHAR(255) NULL COMMENT '비로그인 사용자 식별 토큰 (브라우저/세션 ID)',

    -- 시청 기록 삭제 기능 (유튜브의 "시청 기록에서 삭제" 기능 대응)

    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '시청 일시',
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '수정일시',

    -- 외래키 설정
    CONSTRAINT fk_view_log_video
        FOREIGN KEY (video_id) REFERENCES video (video_id)
            ON DELETE CASCADE ON UPDATE CASCADE,

    CONSTRAINT fk_view_log_user
        FOREIGN KEY (user_id) REFERENCES user (user_id)
            ON DELETE CASCADE ON UPDATE CASCADE,

    -- 대신 조회 성능을 위해 일반 인덱스(INDEX)만 설정

    -- 1. "내 시청 기록" 페이지용 인덱스 (특정 유저가 최근에 본 순서)
    INDEX idx_user_history (user_id, created_at),

    -- 2. "이 영상은 누가 언제 많이 봤나?" 통계용 인덱스
    INDEX idx_video_history (video_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

---

## 11. youtube_recommend (YouTube 영상 추천 제출)

### 기존 테이블 내용(mongoDB)
```javascript
{
  _id: ObjectId("..."),
  rec_index: 1,                            // INT, 추천 고유 번호
  rec_url: "dQw4w9WgXcQ",                 // STRING, YouTube 영상 ID
  rec_real_url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ", // STRING, 전체 URL
  rec_check: 0,                            // INT, 확인 여부 (0: 미확인, 1: 확인)
  rec_date: ISODate("2023-11-29T..."),    // DATETIME, 추천일시
  rec_activate: 7                          // INT, 활성화 상태
}
```

### 리팩토링 후 테이블 내용(mariaDB)
```sql
CREATE TABLE video_request (
    video_request_id    VARCHAR(36) PRIMARY KEY COMMENT '영상 요청 ID (UUID)',

    user_id             VARCHAR(36) NOT NULL COMMENT '요청한 사용자 ID (FK)',
    youtube_url         VARCHAR(50) NOT NULL COMMENT '유튜브 영상 ID (예: dQw4w9WgXcQ)',
    youtube_full_url         VARCHAR(50) NOT NULL COMMENT '유튜브 영상 ID (예: https://www.youtube.com/watch?v=dQw4w9WgXcQ)',

    -- 상태 관리 (단순 0/1보다 명확하게 관리)
    status              ENUM('PENDING', 'ACCEPTED', 'REJECTED')
                        DEFAULT 'PENDING' COMMENT '처리 상태 (대기, 승인, 거절)',

    -- 관리자 코멘트 (거절 사유 등을 적을 수 있게 추가하면 운영에 도움됨)
    admin_comment       VARCHAR(255) NULL COMMENT '관리자 처리 코멘트 (거절 사유 등)',

    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '요청 일시',
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '처리 일시',

    CONSTRAINT fk_request_user
        FOREIGN KEY (user_id) REFERENCES user (user_id)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

---

## 12. comment (댓글)

### 기존 테이블 내용(mongoDB)
```javascript
{
  _id: ObjectId("..."),
  comment_index: 1,                        // INT, 댓글 고유 번호
  youtube_index: 45,                       // INT, 영상 번호
  user_index: 123,                         // INT, 사용자 번호
  comment_date: ISODate("2023-12-01T..."),// DATETIME, 댓글 작성일시
  comment_contents: "좋은 영상입니다!",      // STRING, 댓글 내용
  modify_check: 0,                         // INT, 수정 여부 (0: 원본, 1: 수정됨)
  comment_activate: 7                      // INT, 활성화 상태
}
```

### 리팩토링 후 테이블 내용(mariaDB)
```sql
CREATE TABLE comment (
     comment_id          VARCHAR(36) PRIMARY KEY COMMENT '댓글 ID (UUID)',

     video_id            VARCHAR(36) NOT NULL COMMENT '영상 ID (FK)',
     user_id             VARCHAR(36) NOT NULL COMMENT '작성자 ID (FK)',

     content             TEXT NOT NULL COMMENT '댓글 내용',

    -- 상태 정보
     is_modified         TINYINT(1) DEFAULT 0 COMMENT '수정 여부 (0:원본, 1:수정됨)',
     is_deleted          TINYINT(1) DEFAULT 0 COMMENT '삭제 여부 (0:활성, 1:삭제됨 - 관리자 확인용)',

     created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '작성일시',
     updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '수정일시',

    -- 외래키 설정
     CONSTRAINT fk_comment_video
         FOREIGN KEY (video_id) REFERENCES video (video_id)
             ON DELETE CASCADE ON UPDATE CASCADE,

     CONSTRAINT fk_comment_user
         FOREIGN KEY (user_id) REFERENCES user (user_id)
             ON DELETE CASCADE ON UPDATE CASCADE,

    -- [인덱스 수정] 조회 시 삭제 안 된 것만 가져오므로 인덱스에도 포함하는 게 성능상 유리함
     INDEX idx_video_comments (video_id, is_deleted, created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

---
## 13. like (좋아요)

### 기존 테이블 내용(mongoDB)
```javascript
{
  _id: ObjectId("..."),
  like_index: 1,                           // INT, 좋아요 고유 번호
  youtube_index: 45,                       // INT, 영상 번호
  user_index: 123,                         // INT, 사용자 번호
  like_date: ISODate("2023-12-01T..."),   // DATETIME, 좋아요 일시
  like_activate: 7                         // INT, 활성화 상태 (7: 좋아요, 0: 취소)
}
```

### 리팩토링 후 테이블 내용(mariaDB)
```sql
CREATE TABLE video_like (
    video_like_id       VARCHAR(36) PRIMARY KEY COMMENT '좋아요 ID (UUID)',

    video_id            VARCHAR(36) NOT NULL COMMENT '영상 ID (FK)',
    user_id             VARCHAR(36) NOT NULL COMMENT '사용자 ID (FK)',

    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '좋아요 누른 시간',

    -- [중요] 외래키 설정
    -- 영상이 삭제되거나 유저가 탈퇴하면 좋아요 데이터도 사라져야 함 (Cascade)
    CONSTRAINT fk_like_video
        FOREIGN KEY (video_id) REFERENCES video (video_id)
        ON DELETE CASCADE ON UPDATE CASCADE,

    CONSTRAINT fk_like_user
        FOREIGN KEY (user_id) REFERENCES user (user_id)
        ON DELETE CASCADE ON UPDATE CASCADE,

    -- [핵심] 중복 방지 제약조건
    -- 한 유저가 같은 영상을 두 번 좋아요 누를 수 없음
    -- 이 제약조건 덕분에 DB 레벨에서 중복 클릭이 방어됨
    UNIQUE KEY uk_like_user_video (user_id, video_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

---
