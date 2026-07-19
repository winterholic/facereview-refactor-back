---
title: "FaceReview Legacy Database"
description: "리팩토링 이전 MongoDB 컬렉션과 쿼리 패턴의 역사 기록"
document_type: "historical-reference"
status: "historical"
version: "1.0"
created: "2025-11-28"
updated: "2026-07-19"
source_of_truth:
  - "origin-codes/"
tags: ["database", "mongodb", "legacy", "migration"]
---

# 원본 데이터베이스 구조 분석

> 역사 문서다. 현재 스키마로 사용하지 말고, 마이그레이션 배경 확인에만 사용한다.

## 개요

이 문서는 리팩토링 전 **Face Review** 프로젝트의 원본 MongoDB 데이터베이스 구조를 분석한 문서입니다.

**프로젝트 특성**: YouTube 영상 시청 중 실시간 얼굴 표정 인식을 통해 감정을 분석하고, 이를 기반으로 영상을 추천하는 시스템

**Database**: `FaceReview_Database`

---

## Collections 목록

| Collection | 용도 | 주요 참조 |
|-----------|------|---------|
| user | 사용자 계정 및 프로필 정보 | gate.py, home.py, mypage.py |
| user_profile | 사용자 프로필 (미사용 추정) | gate.py (참조만) |
| youtube_video | YouTube 영상 메타데이터 | 모든 파일 |
| youtube_recommend | 사용자 영상 추천 제출 | register.py |
| video_distribution | 영상별 감정 분포 통계 | home.py, watch.py |
| youtube_watching_data | 사용자 시청 데이터 (감정 분석) | mypage.py, watch.py |
| youtube_watching_timeline | 시청 타임라인 (초단위 감정) | mypage.py |
| youtube_watching_timeline_data | 타임라인 데이터 (초단위 비율) | mypage.py |
| youtube_inquiry | 영상 조회 기록 | home.py, watch.py |
| timeline_emotion_num | 타임라인별 감정 개수 | watch.py |
| timeline_emotion_per | 타임라인별 감정 비율 | watch.py |
| timeline_emotion_most | 타임라인별 주요 감정 | watch.py |
| comment | 영상 댓글 | watch.py |
| like | 영상 좋아요 | watch.py, home.py |

---

## 1. user (사용자 정보)

**용도**: 회원가입, 로그인, 사용자 프로필 관리

**참조 위치**: gate.py:17, home.py:28, mypage.py:27, watch.py:34, admin.py:11

### 스키마 구조

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

### 주요 쿼리 패턴

**회원가입** (gate.py:208):
```javascript
collection_user.insert_one({
  user_index: count + 1,
  user_email_id: email,
  user_pw: hashed_password,
  user_name: name,
  user_favorite_genre_1: genre1,
  user_favorite_genre_2: genre2,
  user_favorite_genre_3: genre3,
  user_create_time: datetime.utcnow(),
  user_role: 1,
  user_point: 0,
  user_profile: 0,
  user_tutorial: 0,
  user_activate: 7
})
```

**로그인** (gate.py:23):
```python
user_document = collection_user.find_one({
  'user_email_id': email_id,
  'user_activate': 7
})
```

**튜토리얼 증가** (gate.py:281):
```javascript
collection_user.update_one(
  {'user_email_id': email_id},
  {'$inc': {'user_tutorial': +1}}
)
```

### 장르 목록

- `drama` - 드라마
- `eating` - 먹방
- `travel` - 여행
- `cook` - 요리
- `show` - 예능
- `information` - 정보
- `fear` - 공포
- `game` - 게임
- `sports` - 스포츠

---

## 2. youtube_video (YouTube 영상 정보)

**용도**: YouTube 영상 메타데이터 저장

**참조 위치**: register.py:12, home.py:29, mypage.py:28, watch.py:35, admin.py:12

### 스키마 구조

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

### 주요 쿼리 패턴

**영상 등록** (admin.py:50):
```javascript
collection_youtube_video.insert_one({
  youtube_index: count + 1,
  youtube_url: url_id,
  youtube_real_url: full_url,
  youtube_title: title,
  youtube_channel: channel,
  youtube_length_hour: hour,
  youtube_length_minute: minute,
  youtube_length_second: second,
  youtube_category: category,
  youtube_create_date: datetime.utcnow(),
  youtube_hits: 0,
  youtube_like: 0,
  youtube_comment_num: 0,
  youtube_activate: 7
})
```

**조회수 증가** (watch.py:636):
```javascript
collection_youtube_video.update_one(
  {'youtube_index': youtube_index},
  {'$inc': {'youtube_hits': +1}}
)
```

**좋아요 증가/감소** (watch.py:883, 940):
```javascript
collection_youtube_video.update_one(
  {'youtube_index': youtube_index, 'youtube_activate': 7},
  {'$inc': {'youtube_like': +1}}  // 또는 -1
)
```

---

## 3. video_distribution (영상별 감정 분포 통계)

**용도**: 각 영상의 감정 분석 통계 데이터 (모든 사용자 집계)

**참조 위치**: home.py:30, watch.py:36, admin.py:13

### 스키마 구조

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

### most_emotion 값

- `neutral` - 무표정
- `happy` - 행복
- `surprise` - 놀람
- `sad` - 슬픔
- `angry` - 화남
- `None` - 데이터 없음

### 주요 쿼리 패턴

**통계 생성** (admin.py:71):
```javascript
collection_video_distribution.insert_one({
  youtube_index: youtube_index,
  watching_data_num: 0,
  video_achivement_avg: 0.0,
  emotion_statistics_avg: {
    neutral: 0.0, happy: 0.0, surprise: 0.0, sad: 0.0, angry: 0.0
  },
  emotion_statistics_score: {
    neutral: 0.0, happy: 0.0, surprise: 0.0, sad: 0.0, angry: 0.0
  },
  most_emotion: 'None',
  distribution_activate: 7
})
```

**조회** (home.py:72):
```python
distribution_document = collection_video_distribution.find_one({
  'youtube_index': youtube_index,
  'distribution_activate': 7
})
```

---

## 4. youtube_watching_data (사용자 시청 데이터)

**용도**: 사용자가 영상을 시청한 기록 및 감정 분석 결과

**참조 위치**: home.py:31, mypage.py:31, watch.py:37, admin.py:14

### 스키마 구조

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

### 주요 쿼리 패턴

**사용자 시청 기록 조회** (mypage.py:59):
```python
recent_video_documents = collection_youtube_watching_data.find({
  'user_index': user_index,
  'watching_data_activate': 7
}).sort({'watching_data_index': -1})
```

**최근 10개 영상** (home.py:125):
```python
recent_documents = collection_youtube_watching_data.find({
  'user_index': user_index
}).sort("date_create_time", -1).limit(10)
```

---

## 5. youtube_watching_timeline (시청 타임라인 - 초단위 감정)

**용도**: 영상 시청 중 매 초마다 인식된 감정 저장

**참조 위치**: mypage.py:32, watch.py:39, admin.py:15

### 스키마 구조

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

### 특징

- **동적 필드**: 영상 길이에 따라 필드가 동적으로 생성됨
- **시간 형식**: `"0:00:01"` ~ `"H:MM:SS"` (문자열)
- **값**: `happy`, `neutral`, `angry`, `sad`, `surprise`

---

## 6. youtube_watching_timeline_data (타임라인 데이터 - 감정 비율)

**용도**: 매 초마다 각 감정의 비율 저장

**참조 위치**: mypage.py:33, admin.py:16

### 스키마 구조

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

### 주요 쿼리 패턴

**타임라인 데이터 조회** (mypage.py:119):
```python
timeline_data_document = collection_youtube_watching_timeline_data.find_one({
  'watching_data_index': watching_data_index,
  'watching_timeline_activate': 7
})

# 특정 시간의 감정 비율
happy_per = timeline_data_document['0:00:05']['happy']
```

---

## 7. timeline_emotion_num (타임라인별 감정 개수)

**용도**: 각 영상의 타임라인별 감정 발생 횟수 집계

**참조 위치**: watch.py:40

### 스키마 구조 (추정)

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

---

## 8. timeline_emotion_per (타임라인별 감정 비율)

**용도**: 각 영상의 타임라인별 감정 비율 (모든 사용자 집계)

**참조 위치**: watch.py:41

### 스키마 구조

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

### 주요 쿼리 패턴

**그래프 데이터 생성** (watch.py:224):
```python
timeline_per_document = collection_timeline_emotion_per.find_one({
  'youtube_index': youtube_index,
  'timeline_emotion_per_activate': 7
})

happy_per = timeline_per_document['0:00:10']['happy'] * 100  # 퍼센트로 변환
```

---

## 9. timeline_emotion_most (타임라인별 주요 감정)

**용도**: 각 영상의 타임라인별 가장 많은 감정

**참조 위치**: watch.py:42

### 스키마 구조 (추정)

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

---

## 10. youtube_inquiry (영상 조회 기록)

**용도**: 사용자별 영상 조회 이력 (중복 조회수 방지, 추천 제외용)

**참조 위치**: home.py:32, watch.py:38

### 스키마 구조

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

### 특징

- **로그인 유저**: `user_id` 사용, `user_token: "None"`
- **비로그인 유저**: `user_token` 사용, `user_id: "None"`
- **용도**:
  - 중복 조회수 방지 (같은 유저가 같은 영상 여러 번 조회 시 조회수 1만 증가)
  - 추천 목록에서 이미 본 영상 제외

### 주요 쿼리 패턴

**로그인 유저 조회 기록 추가** (watch.py:627):
```javascript
collection_youtube_inquiry.insert_one({
  inquiry_index: count + 1,
  youtube_index: youtube_index,
  user_id: email_id,
  user_token: 'None',
  inquiry_activate: 7
})
```

**비로그인 유저 조회 기록 추가** (watch.py:650):
```javascript
collection_youtube_inquiry.insert_one({
  inquiry_index: count + 1,
  youtube_index: youtube_index,
  user_id: 'None',
  user_token: temp_token,
  inquiry_activate: 7
})
```

**추천 시 본 영상 제외** (home.py:248):
```python
youtube_index_documents = collection_youtube_inquiry.find({
  'user_id': user_id
})
youtube_index_list = [doc['youtube_index'] for doc in youtube_index_documents]
# 추천 목록에서 youtube_index_list에 있는 영상 제외
```

---

## 11. youtube_recommend (YouTube 영상 추천 제출)

**용도**: 사용자가 관리자에게 제출한 YouTube 영상 추천

**참조 위치**: register.py:11

### 스키마 구조

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

### 주요 쿼리 패턴

**영상 추천 제출** (register.py:27):
```javascript
collection_youtube_recommend.insert_one({
  rec_index: count + 1,
  rec_url: youtube_url_id,
  rec_real_url: full_url,
  rec_check: 0,
  rec_date: datetime.utcnow(),
  rec_activate: 7
})
```

**미확인 추천 목록 조회** (register.py:42):
```python
rec_documents = collection_youtube_recommend.find({
  'rec_check': 0,
  'rec_activate': 7
})
```

---

## 12. comment (댓글)

**용도**: YouTube 영상에 대한 사용자 댓글

**참조 위치**: watch.py:43

### 스키마 구조

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

### 주요 쿼리 패턴

**댓글 추가** (watch.py:702):
```javascript
collection_comment.insert_one({
  comment_index: count + 1,
  youtube_index: youtube_index,
  user_index: user_index,
  comment_date: datetime.utcnow(),
  comment_contents: contents,
  modify_check: 0,
  comment_activate: 7
})

// 동시에 youtube_video의 comment_num 증가
collection_youtube_video.update_one(
  {'youtube_index': youtube_index},
  {'$inc': {'youtube_comment_num': +1}}
)
```

**댓글 수정** (watch.py:806):
```javascript
collection_comment.update_one(
  {'comment_index': comment_index, 'comment_activate': 7},
  {'$set': {
    'comment_date': datetime.utcnow(),
    'comment_contents': new_contents,
    'modify_check': 1
  }}
)
```

**댓글 삭제** (watch.py:825):
```javascript
collection_comment.update_one(
  {'comment_index': comment_index},
  {'$set': {'comment_activate': 0}}
)

// 동시에 youtube_video의 comment_num 감소
collection_youtube_video.update_one(
  {'youtube_index': youtube_index},
  {'$inc': {'youtube_comment_num': -1}}
)
```

---

## 13. like (좋아요)

**용도**: 사용자의 영상 좋아요

**참조 위치**: watch.py:44, home.py:33

### 스키마 구조

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

### 특징

- 좋아요 취소 시 `like_activate: 0`으로 변경 (삭제하지 않음)
- 재좋아요 시 `like_activate: 7`로 다시 활성화

### 주요 쿼리 패턴

**좋아요 추가** (watch.py:872):
```javascript
collection_like.insert_one({
  like_index: count + 1,
  youtube_index: youtube_index,
  user_index: user_index,
  like_date: datetime.utcnow(),
  like_activate: 7
})

collection_youtube_video.update_one(
  {'youtube_index': youtube_index},
  {'$inc': {'youtube_like': +1}}
)
```

**좋아요 취소** (watch.py:935):
```javascript
collection_like.update_one(
  {'like_index': like_index},
  {'$set': {'like_activate': 0}}
)

collection_youtube_video.update_one(
  {'youtube_index': youtube_index},
  {'$inc': {'youtube_like': -1}}
)
```

**좋아요 개수 조회** (home.py:75):
```python
like_num = collection_like.count_documents({
  'youtube_index': youtube_index,
  'like_activate': 7
})
```

---

## 데이터베이스 관계도

```
user (사용자)
  ├─1:N─> youtube_watching_data (시청 데이터)
  │        ├─1:1─> youtube_watching_timeline (타임라인 감정)
  │        └─1:1─> youtube_watching_timeline_data (타임라인 비율)
  ├─1:N─> youtube_inquiry (조회 기록)
  ├─1:N─> comment (댓글)
  └─1:N─> like (좋아요)

youtube_video (영상)
  ├─1:1─> video_distribution (감정 통계)
  ├─1:1─> timeline_emotion_num (타임라인 감정 개수)
  ├─1:1─> timeline_emotion_per (타임라인 감정 비율)
  ├─1:1─> timeline_emotion_most (타임라인 주요 감정)
  ├─1:N─> youtube_watching_data (시청 데이터)
  ├─1:N─> youtube_inquiry (조회 기록)
  ├─1:N─> comment (댓글)
  └─1:N─> like (좋아요)

youtube_recommend (추천 제출)
  └─(독립적, 관계 없음)
```

---

## 주요 설계 특징

### 1. 활성화 플래그 패턴

모든 컬렉션에 `*_activate` 필드 사용:
- `7`: 활성화 (사용 중)
- `0`: 비활성화 (삭제됨)

**장점**: 데이터 복구 가능, 히스토리 추적
**단점**: 실제 삭제가 아니므로 저장 공간 증가

### 2. 자동증가 인덱스

모든 도큐먼트에 `*_index` 수동 관리:
```python
document_count = collection.count_documents({})
index_max_value = document_count + 1
```

**문제점**:
- Race condition 가능성
- MongoDB의 ObjectId 대신 수동 관리
- 삭제된 데이터 포함 시 중복 가능

### 3. 동적 스키마 (타임라인)

영상 길이에 따라 필드가 동적 생성:
```javascript
{
  "0:00:01": "happy",
  "0:00:02": "neutral",
  // ... 영상 길이만큼
}
```

**문제점**:
- 스키마 일관성 없음
- 쿼리 최적화 어려움
- 인덱싱 불가능

### 4. 중복 데이터 저장

- `youtube_real_url`은 `youtube_url`로 생성 가능
- `youtube_comment_num`, `youtube_like`는 집계 쿼리로 계산 가능
- 데이터 일관성 문제 발생 가능

---

## 리팩토링 시 고려사항

### MariaDB로 마이그레이션할 데이터

**구조화된 관계형 데이터:**
1. ✅ `user` → MariaDB `users` 테이블
2. ✅ `youtube_video` → MariaDB `youtube_videos` 테이블
3. ✅ `youtube_inquiry` → MariaDB `access_logs` 테이블
4. ✅ `comment` → MariaDB `comments` 테이블
5. ✅ `like` → MariaDB `likes` 테이블

### MongoDB에 유지할 데이터

**비정형/대용량 데이터:**
1. ✅ `youtube_watching_data` → MongoDB (감정 분석 결과)
2. ✅ `youtube_watching_timeline` → MongoDB (초단위 타임라인)
3. ✅ `youtube_watching_timeline_data` → MongoDB (초단위 비율)
4. ✅ `video_distribution` → MongoDB (집계 통계)
5. ✅ `timeline_emotion_*` → MongoDB (타임라인 집계)
6. ✅ `youtube_recommend` → MongoDB (임시 데이터)

### 개선 사항

1. **자동증가 인덱스**: MariaDB AUTO_INCREMENT 사용
2. **활성화 플래그**: Soft delete는 필요 시에만
3. **중복 데이터**: 정규화 및 집계 쿼리 활용
4. **동적 스키마**: JSON 타입 또는 별도 테이블 설계
5. **트랜잭션**: 좋아요/댓글 카운트 일관성 보장

---

**작성일**: 2024-01-15
**분석 대상**: gate.py, register.py, home.py, mypage.py, watch.py, admin.py
**다음 단계**: DATABASE.md와 비교하여 마이그레이션 전략 수립
