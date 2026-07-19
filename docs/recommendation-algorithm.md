---
title: "FaceReview Recommendation Algorithm"
description: "현재 2단계 추천 구현과 미구현 고도화 로드맵"
document_type: "architecture-and-roadmap"
status: "partially-implemented"
version: "2.0"
created: "2025-12-19"
updated: "2026-07-19"
source_of_truth:
  - "common/utils/recommendation_alg.py"
  - "app/services/home_service.py"
  - "app/models/mongodb/video_distribution.py"
tags: ["recommendation", "personalization", "ranking", "roadmap"]
---

# FaceReview 추천 알고리즘: 현재 구현과 로드맵

> 4장 이후의 다차원 설계에는 아직 구현되지 않은 로드맵이 포함된다. 현재 동작은 아래 구현 현황과 `source_of_truth` 코드를 기준으로 판단한다.

## 현재 구현 현황 (2026-07-19)

- Tier 1: Celery가 30분마다 사용자 독립 `base_score` 추천 풀을 계산해 Redis에 저장한다.
- Tier 2: 요청 시 상위 150개와 탐색용 무작위 50개만 대상으로 개인 감정·선호 장르·최근 카테고리 보너스를 적용한다.
- 이미 본 영상 제외와 동일 카테고리/대표 감정 연속 노출 제한을 적용한다.
- 협업 필터링, 감정 여정 학습, 사용자별 가중치 학습, A/B 테스트 프레임워크는 미구현이다.

---

## 로드맵 설계

## 1. 개요

### 1.1 목표
감정 데이터를 기반으로 사용자에게 최적화된 영상을 추천하여 사용자 만족도와 체류 시간을 극대화하는 지능형 추천 시스템 구축

### 1.2 핵심 차별점
- **감정 여정 기반 추천**: 단순 매칭이 아닌 사용자의 감정 흐름을 고려한 추천
- **다차원 하이브리드 시스템**: Content-based + Collaborative + Context-aware 결합
- **감정 건강 관리**: 과도한 부정 감정 노출 방지 및 감정 밸런싱
- **고도화된 스코어링**: 6가지 독립적 점수 차원의 가중 합산

---

## 2. 감정 및 카테고리 정의

### 2.1 감정 카테고리 (5종)
- `neutral`: 무표정
- `happy`: 행복
- `surprise`: 놀람
- `sad`: 슬픔
- `angry`: 분노

### 2.2 영상 카테고리 (16종)
`drama`, `eating`, `travel`, `cook`, `show`, `information`, `game`, `sports`, `music`, `animal`, `beauty`, `comedy`, `horror`, `exercise`, `vlog`, `etc`

---

## 3. 카테고리별 감정 가중치 매트릭스

각 카테고리가 유발하는 감정에 대한 기대 가중치를 정의합니다.
가중치는 **0.0 ~ 5.0** 범위이며, 높을수록 해당 감정과의 연관성이 강합니다.

### 3.1 기존 카테고리 가중치 (개선)

#### Drama (드라마)
```python
{
    'neutral': 0.5,
    'happy': 2.5,
    'surprise': 2.0,
    'sad': 3.0,
    'angry': 2.0
}
# 특징: 감정 스펙트럼이 넓고 슬픔과 행복이 주요 감정
```

#### Eating (먹방)
```python
{
    'neutral': 1.0,
    'happy': 4.0,
    'surprise': 2.5,
    'sad': 0.2,
    'angry': 0.5
}
# 특징: 행복과 놀람이 주요 감정 (맛있는 음식에 대한 반응)
```

#### Travel (여행)
```python
{
    'neutral': 0.8,
    'happy': 3.5,
    'surprise': 3.0,
    'sad': 0.5,
    'angry': 0.3
}
# 특징: 새로운 경험에 대한 행복과 놀람
```

#### Cook (요리)
```python
{
    'neutral': 2.5,
    'happy': 3.0,
    'surprise': 1.5,
    'sad': 0.3,
    'angry': 0.5
}
# 특징: 차분한 무표정 상태로 집중하며 결과물에 행복
```

#### Show (예능)
```python
{
    'neutral': 0.3,
    'happy': 4.5,
    'surprise': 2.5,
    'sad': 1.0,
    'angry': 0.8
}
# 특징: 웃음과 즐거움이 주요 감정
```

#### Information (정보/교양)
```python
{
    'neutral': 3.0,
    'happy': 1.5,
    'surprise': 2.5,
    'sad': 0.5,
    'angry': 1.5
}
# 특징: 집중하는 무표정 상태, 새로운 정보에 놀람
```

#### Horror (공포)
```python
{
    'neutral': 0.5,
    'happy': 0.3,
    'surprise': 5.0,
    'sad': 1.5,
    'angry': 2.0
}
# 특징: 놀람이 압도적으로 높음
```

#### Exercise (운동)
```python
{
    'neutral': 2.0,
    'happy': 3.5,
    'surprise': 1.5,
    'sad': 0.5,
    'angry': 1.5
}
```

#### Vlog (브이로그)
```python
{
    'neutral': 2.5,
    'happy': 2.5,
    'surprise': 1.5,
    'sad': 1.5,
    'angry': 1.0
}
```

#### Game (게임)
```python
{
    'neutral': 1.5,
    'happy': 3.0,
    'surprise': 2.5,
    'sad': 1.5,
    'angry': 2.5
}
# 특징: 승패에 따른 다양한 감정 표출
```

#### Sports (스포츠)
```python
{
    'neutral': 1.0,
    'happy': 3.5,
    'surprise': 4.0,
    'sad': 1.0,
    'angry': 1.5
}
# 특징: 극적인 순간의 놀람과 승리의 기쁨
```

### 3.2 신규 카테고리 가중치

#### Music (음악)
```python
{
    'neutral': 1.5,
    'happy': 4.0,
    'surprise': 2.0,
    'sad': 2.5,
    'angry': 1.0
}
# 특징: 장르에 따라 다양하나 주로 행복과 감동(슬픔)
# 발라드는 sad 높음, 댄스는 happy 높음
```

#### Animal (동물)
```python
{
    'neutral': 1.0,
    'happy': 4.5,
    'surprise': 3.0,
    'sad': 0.8,
    'angry': 0.2
}
# 특징: 귀여움에 대한 행복과 예상 밖 행동에 놀람
```

#### Beauty (뷰티/패션)
```python
{
    'neutral': 2.0,
    'happy': 3.5,
    'surprise': 2.5,
    'sad': 0.5,
    'angry': 0.5
}
# 특징: 변화 결과에 대한 만족감, 집중하는 무표정
```

#### Comedy (코미디)
```python
{
    'neutral': 0.2,
    'happy': 5.0,
    'surprise': 2.0,
    'sad': 0.3,
    'angry': 0.5
}
# 특징: 웃음이 핵심, happy 점수 최고
```

#### Etc (기타)
```python
{
    'neutral': 2.5,
    'happy': 2.0,
    'surprise': 2.0,
    'sad': 1.5,
    'angry': 1.5
}
# 특징: 균형잡힌 감정 분포 (예측 불가능한 콘텐츠)
```

---

## 4. 다차원 스코어링 시스템

총 점수는 6개 독립 차원의 가중 합산으로 계산됩니다.

### 4.1 개인화 점수 (Personalization Score) - 가중치: 35%

#### 4.1.1 최근 감정 패턴 매칭 (0~40점)
```python
# 최근 10개 시청 영상의 감정 패턴 분석
recent_emotion_pattern = analyze_recent_10_videos(user_id)

# 시간 가중 적용 (최근일수록 높은 가중치)
time_weights = [1.5, 1.4, 1.3, 1.2, 1.15, 1.1, 1.05, 1.0, 0.95, 0.9]

score = 0
for i, video in enumerate(recent_videos):
    user_emotion = video.user_most_emotion
    video_avg_emotion = video.video_distribution.most_emotion

    # 완전 일치: 4점 * 시간 가중치
    if user_emotion == video_avg_emotion:
        score += 4 * time_weights[i]
    # 부분 일치 (사용자 또는 평균 중 하나): 2점 * 시간 가중치
    else:
        score += 2 * time_weights[i]

# 정규화 (0~40점)
personalization_score += min(score, 40)
```

#### 4.1.2 선호 카테고리 매칭 (0~30점)
```python
favorite_categories = [user.favorite_genre_1, user.favorite_genre_2, user.favorite_genre_3]

if video.category == favorite_categories[0]:
    personalization_score += 15  # 1순위 선호
elif video.category == favorite_categories[1]:
    personalization_score += 10  # 2순위 선호
elif video.category == favorite_categories[2]:
    personalization_score += 5   # 3순위 선호
```

#### 4.1.3 감정 친화도 점수 (0~30점)
```python
# 사용자의 전체 시청 이력에서 각 감정별 선호도 계산
user_emotion_preference = calculate_emotion_preference(user_id)
# 예: {'happy': 0.35, 'surprise': 0.25, 'neutral': 0.20, 'sad': 0.15, 'angry': 0.05}

# 영상의 감정 분포와 사용자 선호도의 유사도 계산 (코사인 유사도)
video_emotion_distribution = {
    'happy': video.emotion_statistics_avg_happy,
    'surprise': video.emotion_statistics_avg_surprise,
    'neutral': video.emotion_statistics_avg_neutral,
    'sad': video.emotion_statistics_avg_sad,
    'angry': video.emotion_statistics_avg_angry
}

similarity = cosine_similarity(user_emotion_preference, video_emotion_distribution)
personalization_score += similarity * 30  # 0~30점
```

### 4.2 품질 점수 (Quality Score) - 가중치: 25%

#### 4.2.1 참여도 기반 점수 (0~50점)
```python
# 시청 완료율
achievement_score = 0
if video.video_achivement_avg >= 95:
    achievement_score = 25
elif video.video_achivement_avg >= 90:
    achievement_score = 20
elif video.video_achivement_avg >= 80:
    achievement_score = 15
elif video.video_achivement_avg >= 70:
    achievement_score = 10
elif video.video_achivement_avg >= 50:
    achievement_score = 5
else:
    achievement_score = 0

# 무표정 비율 페널티 (표정 변화가 적으면 지루한 콘텐츠)
neutral_penalty = 0
if video.watching_data_num > 3:  # 충분한 샘플 수
    neutral_per = video.emotion_statistics_avg_neutral
    if neutral_per >= 99.9:
        neutral_penalty = -25
    elif neutral_per >= 98:
        neutral_penalty = -15
    elif neutral_per >= 96:
        neutral_penalty = -10
    elif neutral_per >= 95:
        neutral_penalty = -5
    elif neutral_per < 70:  # 적절한 감정 표현
        neutral_penalty = 5

quality_score = achievement_score + neutral_penalty
quality_score = max(0, min(quality_score, 50))  # 0~50점 범위
```

#### 4.2.2 인기도 점수 (0~50점)
```python
# 로그 스케일 조회수 점수 (0~30점)
import math
if video.youtube_hits > 0:
    view_score = min(5 * (1 + math.sqrt(video.youtube_hits) * 0.05 * math.log10(video.youtube_hits)), 30)
else:
    view_score = 0

# 로그 스케일 좋아요 점수 (0~20점)
if video.youtube_like > 0:
    like_score = min(1 + math.sqrt(video.youtube_like) * 0.05 * math.log10(video.youtube_like), 20)
else:
    like_score = 0

quality_score += view_score + like_score  # 최대 50점 추가
```

### 4.3 신선도 점수 (Freshness Score) - 가중치: 15%

```python
from datetime import datetime, timedelta

current_date = datetime.now()
upload_date = video.youtube_create_date
days_passed = (current_date - upload_date).days

# 업로드 후 경과 일수에 따른 점수
if days_passed <= 1:
    freshness_score = 100
elif days_passed <= 3:
    freshness_score = 80
elif days_passed <= 7:
    freshness_score = 60
elif days_passed <= 14:
    freshness_score = 40
elif days_passed <= 30:
    freshness_score = 20
else:
    # 30일 이후는 지수 감소
    freshness_score = max(20 * math.exp(-0.01 * days_passed), 5)
```

### 4.4 컨텍스트 점수 (Context Score) - 가중치: 10%

```python
# 시청 시간대 및 패턴 기반 추천
current_hour = datetime.now().hour
current_day_of_week = datetime.now().weekday()  # 0=월요일, 6=일요일

context_score = 0

# 시간대별 카테고리 선호도 (사용자별 통계 필요)
user_time_preference = get_user_time_category_preference(user_id, current_hour)
if video.category in user_time_preference['top_categories']:
    context_score += 30

# 요일별 패턴 (주중/주말)
is_weekend = current_day_of_week >= 5
user_day_preference = get_user_day_category_preference(user_id, is_weekend)
if video.category in user_day_preference['top_categories']:
    context_score += 20

# 세션 내 다양성 보너스
# 최근 5개 추천 영상과 카테고리가 다르면 가산점
recent_recommended_categories = get_recent_recommended_categories(user_id, limit=5)
if video.category not in recent_recommended_categories:
    context_score += 30
else:
    # 같은 카테고리가 연속되면 감점
    context_score -= 10

context_score = max(0, min(context_score, 100))
```

### 4.5 협업 필터링 점수 (Collaborative Score) - 가중치: 10%

```python
# 유사 사용자 기반 추천
similar_users = find_similar_users(user_id, limit=20)
# 유사도 계산: 감정 선호도 + 카테고리 선호도 기반

collaborative_score = 0
for similar_user in similar_users:
    # 유사 사용자가 이 영상을 시청하고 높은 만족도를 보였는지 확인
    watch_log = get_watch_log(similar_user.user_id, video.youtube_index)
    if watch_log:
        # 시청 완료율과 유사도를 곱하여 점수 계산
        collaborative_score += watch_log.achievement * similar_user.similarity_score

# 정규화 (0~100점)
collaborative_score = min(collaborative_score / len(similar_users) * 5, 100)
```

### 4.6 다양성 점수 (Diversity Score) - 가중치: 5%

```python
# 필터 버블 방지를 위한 다양성 보장
user_category_distribution = get_user_category_distribution(user_id)
# 예: {'game': 0.4, 'show': 0.3, 'drama': 0.2, 'sports': 0.1}

# 사용자가 적게 본 카테고리에 보너스
category_exposure = user_category_distribution.get(video.category, 0)
if category_exposure < 0.05:  # 5% 미만 노출
    diversity_score = 100  # 세렌디피티 발견 기회
elif category_exposure < 0.10:
    diversity_score = 70
elif category_exposure < 0.15:
    diversity_score = 40
elif category_exposure < 0.25:
    diversity_score = 20
else:
    diversity_score = 0

# 감정 다양성 보너스
user_emotion_distribution = get_user_emotion_distribution(user_id)
emotion_balance_penalty = calculate_emotion_imbalance(user_emotion_distribution)
# 특정 감정에 편중되어 있으면 다른 감정 영상에 보너스
diversity_score += emotion_balance_penalty
diversity_score = max(0, min(diversity_score, 100))
```

---

## 5. 최종 점수 계산

### 5.1 가중 합산
```python
WEIGHTS = {
    'personalization': 0.35,
    'quality': 0.25,
    'freshness': 0.15,
    'context': 0.10,
    'collaborative': 0.10,
    'diversity': 0.05
}

final_score = (
    personalization_score * WEIGHTS['personalization'] +
    quality_score * WEIGHTS['quality'] +
    freshness_score * WEIGHTS['freshness'] +
    context_score * WEIGHTS['context'] +
    collaborative_score * WEIGHTS['collaborative'] +
    diversity_score * WEIGHTS['diversity']
)
```

### 5.2 감정 건강 조절 (Emotion Health Adjustment)
```python
# 사용자의 최근 감정 이력 확인
recent_emotion_history = get_recent_emotion_history(user_id, days=7)

# 부정 감정(sad, angry) 과다 노출 감지
negative_emotion_ratio = (
    recent_emotion_history['sad'] + recent_emotion_history['angry']
) / sum(recent_emotion_history.values())

# 30% 이상 부정 감정 노출 시 조정
if negative_emotion_ratio > 0.3:
    # 긍정 감정(happy) 영상 우선 순위 상승
    if video.most_emotion == 'happy':
        final_score *= 1.3
    elif video.most_emotion in ['sad', 'angry']:
        final_score *= 0.7

# 무표정(neutral) 과다 노출 감지
if recent_emotion_history['neutral'] > 0.5:
    # 감정 표현이 풍부한 영상 우선 순위 상승
    if video.emotion_statistics_avg_neutral < 0.7:
        final_score *= 1.2
```

### 5.3 개인별 가중치 조정 (User Preference Learning)
```python
# 사용자의 클릭률(CTR)과 시청 완료율 기반 학습
user_weight_adjustment = learn_user_weight_preference(user_id)
# 예: {'personalization': 1.1, 'quality': 0.9, 'freshness': 1.2, ...}

# 개인화된 가중치 적용
for key, base_weight in WEIGHTS.items():
    WEIGHTS[key] = base_weight * user_weight_adjustment.get(key, 1.0)

# 재정규화
total_weight = sum(WEIGHTS.values())
WEIGHTS = {k: v/total_weight for k, v in WEIGHTS.items()}
```

---

## 6. 고급 기능

### 6.1 감정 여정 추천 (Emotional Journey)
```python
# 사용자의 감정 변화 패턴 학습
emotion_transition_matrix = build_emotion_transition_matrix(user_id)
# 예: happy 시청 후 surprise로 이동하는 경향 60%

current_emotion = get_current_session_emotion(user_id)
next_preferred_emotion = emotion_transition_matrix[current_emotion].most_likely()

# 다음 추천 영상을 선호 감정에 맞춰 조정
if video.most_emotion == next_preferred_emotion:
    final_score *= 1.25
```

### 6.2 세렌디피티 추천 (Serendipity)
```python
# 10% 확률로 예상 밖의 카테고리 추천 (탐색)
import random
if random.random() < 0.1:
    # 사용자가 한 번도 본 적 없는 카테고리
    unexplored_categories = get_unexplored_categories(user_id)
    if video.category in unexplored_categories:
        final_score += 20  # 탐색 보너스
```

### 6.3 콜드 스타트 해결

#### 6.3.1 신규 사용자
```python
if user.total_watch_count < 5:
    # 회원가입 시 선택한 선호 장르 기반 추천
    if video.category in user.initial_favorite_genres:
        final_score *= 1.5

    # 인기 영상 우선 추천 (품질 점수 가중치 증가)
    WEIGHTS['quality'] = 0.50
    WEIGHTS['personalization'] = 0.10
```

#### 6.3.2 신규 영상
```python
if video.watching_data_num < 3:
    # 충분한 감정 데이터가 없으면 카테고리 기반 추정
    category_emotion_weight = CATEGORY_EMOTION_WEIGHTS[video.category]
    estimated_emotion_distribution = category_emotion_weight

    # 추정 분포 사용
    video.estimated_emotion_statistics_avg = estimated_emotion_distribution

    # 신규 영상 탐색 보너스
    final_score += 15
```

### 6.4 재추천 방지 (De-duplication)
```python
# 이미 본 영상 제외
viewed_videos = get_viewed_videos(user_id)
if video.youtube_index in viewed_videos:
    return None  # 추천 목록에서 제외

# 최근 추천했지만 클릭하지 않은 영상 페널티
recently_recommended = get_recently_recommended_not_clicked(user_id, days=7)
if video.youtube_index in recently_recommended:
    final_score *= 0.5  # 관심 없음으로 간주
```

---

## 7. 추천 리스트 구성 전략

### 7.1 다양성 보장 리랭킹
```python
# 상위 100개 후보 영상 선정
top_candidates = get_top_videos_by_score(user_id, limit=100)

# 최종 20개 선정 시 다양성 보장
final_recommendations = []
selected_categories = []
selected_emotions = []

for video in top_candidates:
    # 같은 카테고리 연속 2개 이상 방지
    if selected_categories[-2:].count(video.category) >= 2:
        continue

    # 같은 감정 연속 3개 이상 방지
    if selected_emotions[-3:].count(video.most_emotion) >= 3:
        continue

    final_recommendations.append(video)
    selected_categories.append(video.category)
    selected_emotions.append(video.most_emotion)

    if len(final_recommendations) >= 20:
        break
```

### 7.2 첫 번째 추천의 중요성
```python
# 첫 번째 추천은 클릭률이 가장 높은 영상 배치
# 사용자별 클릭 패턴 학습 데이터 활용
first_recommendation = get_highest_ctr_prediction(user_id, top_candidates)
final_recommendations[0] = first_recommendation
```

### 7.3 A/B 테스팅 슬롯
```python
# 20개 중 2개는 실험 슬롯 (10%)
experiment_slots = [5, 15]  # 6번째, 16번째 위치
for slot in experiment_slots:
    # 새로운 알고리즘 또는 가설 검증용 추천
    experimental_video = get_experimental_recommendation(user_id)
    final_recommendations[slot] = experimental_video
```

---

## 8. 성능 최적화

### 8.1 캐싱 전략
```python
# 영상별 기본 점수 캐싱 (1시간)
@cache(timeout=3600)
def calculate_base_video_score(video_index):
    # 품질 점수, 신선도 점수 등 사용자 독립적 점수
    return quality_score + freshness_score

# 사용자별 선호도 캐싱 (30분)
@cache(timeout=1800)
def get_user_preference_profile(user_id):
    return {
        'emotion_preference': ...,
        'category_preference': ...,
        'time_pattern': ...
    }
```

### 8.2 배치 처리
```python
# 인기 영상 추천 리스트 사전 계산 (매시간)
def precompute_popular_recommendations():
    for category in ALL_CATEGORIES:
        top_videos = get_category_top_videos(category, limit=50)
        cache.set(f'popular_{category}', top_videos, timeout=3600)
```

### 8.3 점진적 로딩
```python
# 첫 5개는 즉시 반환, 나머지는 백그라운드 계산
quick_recommendations = get_quick_recommendations(user_id, limit=5)
background_task.delay('calculate_full_recommendations', user_id, limit=20)
```

---

## 9. 평가 지표 (Metrics)

### 9.1 온라인 지표
- **CTR (Click-Through Rate)**: 추천 영상 클릭률
- **시청 완료율**: 추천 영상의 평균 시청 완료율
- **세션 시간**: 추천으로 인한 평균 세션 시간 증가
- **재방문율**: 추천 시스템 만족도에 따른 재방문

### 9.2 오프라인 지표
- **정확도 (Precision@K)**: 상위 K개 추천의 적중률
- **다양성 (Diversity)**: 추천 리스트의 카테고리/감정 분포 엔트로피
- **참신성 (Novelty)**: 사용자가 처음 접하는 콘텐츠 비율
- **커버리지 (Coverage)**: 전체 영상 중 추천되는 영상 비율

### 9.3 A/B 테스트 프레임워크
```python
# 실험군 vs 대조군
experiment_groups = {
    'control': '기존 알고리즘',
    'test_a': '신규 알고리즘 버전 A',
    'test_b': '신규 알고리즘 버전 B'
}

# 사용자를 그룹별로 분할 (해시 기반)
user_group = assign_experiment_group(user_id)
recommendations = get_recommendations(user_id, algorithm=user_group)

# 성과 추적
track_metrics(user_id, user_group, recommendations)
```

---

## 10. 구현 우선순위

### Phase 1: 핵심 알고리즘 (1-2주)
1. 카테고리별 감정 가중치 매트릭스 구현
2. 다차원 스코어링 시스템 구현 (6가지 점수)
3. 최종 점수 계산 및 랭킹

### Phase 2: 개인화 고도화 (2-3주)
1. 협업 필터링 구현 (유사 사용자 탐색)
2. 컨텍스트 인식 (시간/요일 패턴)
3. 감정 여정 추천

### Phase 3: 고급 기능 (2-3주)
1. 감정 건강 조절 시스템
2. 세렌디피티 추천
3. 콜드 스타트 해결
4. 재추천 방지

### Phase 4: 최적화 및 평가 (1-2주)
1. 캐싱 및 성능 최적화
2. A/B 테스팅 프레임워크
3. 지표 모니터링 대시보드

---

## 11. 기대 효과

### 11.1 사용자 경험
- **개인화 정확도 향상**: 감정 기반 정밀 매칭으로 만족도 증가
- **발견의 즐거움**: 세렌디피티 추천으로 새로운 콘텐츠 탐색
- **감정 건강 관리**: 과도한 부정 감정 노출 방지

### 11.2 비즈니스 성과
- **체류 시간 증가**: 정확한 추천으로 세션 시간 30% 이상 증가 예상
- **재방문율 향상**: 맞춤형 추천으로 사용자 충성도 증가
- **콘텐츠 커버리지 향상**: 롱테일 콘텐츠 노출 기회 증가

### 11.3 차별화 포인트
- **감정 중심 추천**: 단순 시청 기록이 아닌 실시간 감정 반응 활용
- **하이브리드 접근**: 6가지 독립 차원의 종합적 평가
- **사용자 건강 고려**: Netflix, YouTube에는 없는 감정 밸런싱 기능

---

## 부록 A: 데이터 스키마 요구사항

### A.1 필요한 추가 데이터
```python
# 사용자 선호도 프로필 (캐시)
user_preference_profile = {
    'user_id': str,
    'emotion_preference': dict,  # {'happy': 0.35, ...}
    'category_preference': dict,  # {'game': 0.4, ...}
    'time_category_pattern': dict,  # {0: ['game'], 1: ['game'], ...}
    'day_category_pattern': dict,  # {'weekday': [...], 'weekend': [...]}
    'emotion_transition_matrix': dict,  # {'happy': {'surprise': 0.6, ...}, ...}
    'last_updated': datetime
}

# 추천 이력
recommendation_history = {
    'user_id': str,
    'video_index': str,
    'recommended_at': datetime,
    'clicked': bool,
    'watched': bool,
    'watch_duration': int,
    'experiment_group': str  # A/B 테스트용
}

# 유사 사용자 매트릭스 (사전 계산)
similar_users_cache = {
    'user_id': str,
    'similar_users': [
        {'user_id': str, 'similarity_score': float},
        ...
    ],
    'last_updated': datetime
}
```

---

## 부록 B: 카테고리별 추천 전략 요약

| 카테고리 | 주요 감정 | 추천 시간대 | 특이사항 |
|---------|---------|-----------|---------|
| Comedy | Happy (5.0) | 저녁 7-10시 | 스트레스 해소 목적 |
| Fear | Surprise (5.0) | 밤 10시-새벽 | 연령 제한 고려 |
| Animal | Happy (4.5) | 오후 2-5시 | 힐링 목적, 재시청률 높음 |
| Show | Happy (4.5) | 저녁 6-9시 | 식사 시간대 선호 |
| Eating | Happy (4.0) | 점심/저녁 시간 | 식사 전후 선호 |
| Music | Happy (4.0), Sad (2.5) | 다양 | 장르 세분화 필요 |
| Sports | Surprise (4.0) | 저녁 8-11시 | 실시간 이벤트 연동 |
| Travel | Happy (3.5), Surprise (3.0) | 주말 오후 | 계절성 고려 |
| Beauty | Happy (3.5) | 오후 3-6시 | 여성 사용자 선호 |
| Information | Neutral (3.0) | 오전 9-12시 | 학습 목적, 긴 시청 시간 |
| Drama | Sad (3.0), Happy (2.5) | 밤 9시-새벽 | 에피소드 연속 시청 패턴 |
| Game | Happy (3.0), Angry (2.5) | 오후-밤 | 게임 유행 반영 필요 |
| Cook | Happy (3.0), Neutral (2.5) | 오후 4-7시 | 실용적 목적 |
| Etc | 균형 | 다양 | 실험적 콘텐츠 |

---

## 변경 이력
- v1.0 (2024-XX-XX): 초안 작성
  - 14개 카테고리 감정 가중치 정의
  - 6차원 스코어링 시스템 설계
  - 감정 건강 조절 메커니즘 추가
  - 구현 우선순위 및 기대 효과 정리
