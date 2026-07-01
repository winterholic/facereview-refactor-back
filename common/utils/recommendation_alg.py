import math
import random
from datetime import datetime
from typing import List, Dict

#NOTE: 감정 기반 추천 점수 알고리즘 (경주마 2단 구조)
#      Tier1(오프라인/Celery): 유저 무관 영상 본질 점수(base_score)로 상위 풀을 미리 계산
#      Tier2(요청시/경량): base_score 풀 위에 개인 감정 가산점만 얹어 순간 재정렬

EMOTIONS = ['neutral', 'happy', 'surprise', 'sad', 'angry']
NON_NEUTRAL = ['happy', 'surprise', 'sad', 'angry']

#NOTE: base_score 구성 가중치 (합=1.0, 각 요소 0~1 정규화)
#      앞 3개(감정 각성/대표감정 강도/완주율)는 시청자로부터 나온 신호 → 신뢰도(shrinkage) 곱셈 대상
#      뒤 2개(인기/신선도)는 외부 신호 → 표본과 무관하므로 곱하지 않음
BASE_WATCHER_WEIGHTS = {'engagement': 0.30, 'peak': 0.22, 'completion': 0.23}
BASE_EXTERNAL_WEIGHTS = {'popularity': 0.15, 'freshness': 0.10}

#NOTE: 표본 신뢰도 shrinkage 상수. conf = frames / (frames + K)
#      프레임은 약 2fps 누적이므로 3분 1회 완주 ≈ 360프레임. K=200이면 1회 완주에 conf≈0.64
CONFIDENCE_K = 200

#NOTE: 개인화 가산점 가중치 (base_score 0~100 위에 얹는 additive, 최대 ~60)
PERSONAL_AFFINITY_WEIGHT = 25.0     # 유저 감정 프로필 ↔ 영상 감정 분포 코사인
PERSONAL_DOMINANT_WEIGHT = 15.0     # 영상 대표감정을 유저가 평소 얼마나 느끼는가
FAVORITE_GENRE_BONUS = [12.0, 8.0, 5.0]   # 선호 장르 1·2·3순위
RECENT_CATEGORY_BONUS_MAX = 8.0     # 최근 본 카테고리 연속성

RECENCY_DECAY = 0.88


def emotion_cosine(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
    a = [vec_a.get(e, 0.0) for e in EMOTIONS]
    b = [vec_b.get(e, 0.0) for e in EMOTIONS]
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(y * y for y in b))
    return dot / (mag_a * mag_b) if (mag_a and mag_b) else 0.0


def _popularity_score(view_count: int, like_count: int) -> float:
    views = max(int(view_count or 0), 0)
    likes = max(int(like_count or 0), 0)
    view_part = min(math.log10(views + 1) / 6.0, 1.0)   # 10^6 조회 → 1.0
    like_part = min(math.log10(likes + 1) / 4.0, 1.0)   # 10^4 좋아요 → 1.0
    return view_part * 0.6 + like_part * 0.4


def _freshness_score(created_at) -> float:
    if not created_at:
        return 0.3
    if isinstance(created_at, str):
        try:
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        except ValueError:
            return 0.3
    if created_at.tzinfo is not None:
        created_at = created_at.replace(tzinfo=None)
    days = (datetime.utcnow() - created_at).days
    if days <= 2:
        return 1.0
    if days <= 7:
        return 0.8
    if days <= 14:
        return 0.6
    if days <= 30:
        return 0.4
    return max(0.3 * math.exp(-0.02 * days), 0.1)


def compute_base_score(stats: Dict) -> float:
    #NOTE: 장르 무관 영상 본질 점수. 감정을 강하게 유발하고, 끝까지 보게 하며, 검증된(표본충분) 영상일수록 높음
    emotion_dist = stats.get('emotion_distribution') or {}
    neutral = emotion_dist.get('neutral', 0.0)
    engagement = max(0.0, min(1.0 - neutral, 1.0))              # 무표정이 아닐수록 감정 각성
    peak = max((emotion_dist.get(e, 0.0) for e in NON_NEUTRAL), default=0.0)  # 대표(비무표정) 감정 강도
    completion = max(0.0, min(float(stats.get('average_completion_rate') or 0.0), 1.0))

    frames = int(stats.get('sample_frames') or 0)
    confidence = frames / (frames + CONFIDENCE_K) if frames > 0 else 0.0

    watcher = (
        BASE_WATCHER_WEIGHTS['engagement'] * engagement +
        BASE_WATCHER_WEIGHTS['peak'] * peak +
        BASE_WATCHER_WEIGHTS['completion'] * completion
    )
    external = (
        BASE_EXTERNAL_WEIGHTS['popularity'] * _popularity_score(stats.get('view_count'), stats.get('like_count')) +
        BASE_EXTERNAL_WEIGHTS['freshness'] * _freshness_score(stats.get('created_at'))
    )
    return round(100.0 * (confidence * watcher + external), 4)


def build_user_emotion_profile(recent_watching: List[Dict]) -> Dict[str, float]:
    #NOTE: 유저가 최근 시청에서 실제로 느낀 감정(emotion_percentages)의 recency-decay 평균 → 정규화 벡터
    if not recent_watching:
        return {e: (0.0 if e == 'neutral' else 0.25) for e in EMOTIONS}
    acc = {e: 0.0 for e in EMOTIONS}
    for idx, d in enumerate(recent_watching):
        weight = RECENCY_DECAY ** idx
        for e, pct in (d.get('emotion_percentages') or {}).items():
            if e in acc:
                acc[e] += pct * weight
    total = sum(acc.values())
    if total <= 0:
        return {e: (0.0 if e == 'neutral' else 0.25) for e in EMOTIONS}
    return {e: v / total for e, v in acc.items()}


def _personal_bonus(video: Dict, user_profile: Dict[str, float],
                    favorite_genres: List[str], recent_category_weight: Dict[str, float]) -> float:
    bonus = 0.0

    #NOTE: 유저 감정 프로필 ↔ 영상 감정 분포 궁합 (공포러버 → 고-surprise 영상 부스트)
    video_emo = video.get('emotion_distribution') or {}
    if video_emo:
        bonus += emotion_cosine(user_profile, video_emo) * PERSONAL_AFFINITY_WEIGHT
        dominant = video.get('dominant_emotion')
        if dominant:
            bonus += user_profile.get(dominant, 0.0) * PERSONAL_DOMINANT_WEIGHT

    #NOTE: 선호 장르 가산 (순위 차등)
    cat = video.get('category')
    if cat in favorite_genres:
        rank = favorite_genres.index(cat)
        bonus += FAVORITE_GENRE_BONUS[min(rank, len(FAVORITE_GENRE_BONUS) - 1)]

    #NOTE: 최근 본 카테고리 연속성 (몰입 흐름 유지)
    if recent_category_weight:
        bonus += min(recent_category_weight.get(cat, 0.0), 1.0) * RECENT_CATEGORY_BONUS_MAX

    return bonus


def rank_personalized(pool: List[Dict], recent_watching: List[Dict], favorite_genres: List[str],
                      viewed_ids: set, limit: int = 20,
                      top_n: int = 150, random_n: int = 50) -> List[Dict]:
    #NOTE: pool은 base_score 내림차순으로 미리 정렬된 상위 풀. 여기서 상위 top_n + 나머지 랜덤 random_n만 경량 재정렬
    viewed_ids = viewed_ids or set()
    fresh_pool = [v for v in pool if v.get('video_id') not in viewed_ids]
    if not fresh_pool:
        return []

    head = fresh_pool[:top_n]
    tail = fresh_pool[top_n:]
    explore = random.sample(tail, min(random_n, len(tail))) if tail else []
    candidates = head + explore

    user_profile = build_user_emotion_profile(recent_watching)

    #NOTE: 최근 시청 카테고리 recency-decay 가중치 (0~1 정규화)
    recent_category_weight: Dict[str, float] = {}
    for idx, d in enumerate(recent_watching[:10]):
        cat = d.get('category')
        if cat:
            recent_category_weight[cat] = recent_category_weight.get(cat, 0.0) + RECENCY_DECAY ** idx
    if recent_category_weight:
        top_w = max(recent_category_weight.values())
        recent_category_weight = {k: v / top_w for k, v in recent_category_weight.items()}

    scored = []
    for v in candidates:
        final = v.get('base_score', 0.0) + _personal_bonus(v, user_profile, favorite_genres, recent_category_weight)
        scored.append((final, v))
    scored.sort(key=lambda x: x[0], reverse=True)

    #NOTE: 가벼운 다양성 필터 - 같은 카테고리/대표감정이 연속 3개 이상 몰리지 않게
    result, cats, emos, selected = [], [], [], set()
    for _, v in scored:
        cat = v.get('category')
        emo = v.get('dominant_emotion', 'neutral')
        if (len(cats) >= 2 and cats[-2:].count(cat) >= 2) or (len(emos) >= 3 and emos[-3:].count(emo) >= 3):
            continue
        result.append(v)
        selected.add(v.get('video_id'))
        cats.append(cat)
        emos.append(emo)
        if len(result) >= limit:
            return result

    #NOTE: 다양성 필터로 부족하면 남은 상위 후보로 채움
    for _, v in scored:
        if v.get('video_id') in selected:
            continue
        result.append(v)
        selected.add(v.get('video_id'))
        if len(result) >= limit:
            break
    return result
