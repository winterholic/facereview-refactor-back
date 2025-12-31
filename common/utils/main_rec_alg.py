import math
from datetime import datetime
from typing import List, Dict

#NOTE: AI가 생성해 준 개인화 로직

CATEGORY_WEIGHTS = {
    'drama': {'neutral': 0.5, 'happy': 2.5, 'surprise': 2.0, 'sad': 3.0, 'angry': 2.0},
    'eating': {'neutral': 1.0, 'happy': 4.0, 'surprise': 2.5, 'sad': 0.2, 'angry': 0.5},
    'travel': {'neutral': 0.8, 'happy': 3.5, 'surprise': 3.0, 'sad': 0.5, 'angry': 0.3},
    'cook': {'neutral': 2.5, 'happy': 3.0, 'surprise': 1.5, 'sad': 0.3, 'angry': 0.5},
    'show': {'neutral': 0.3, 'happy': 4.5, 'surprise': 2.5, 'sad': 1.0, 'angry': 0.8},
    'information': {'neutral': 3.0, 'happy': 1.5, 'surprise': 2.5, 'sad': 0.5, 'angry': 1.5},
    'horror': {'neutral': 0.5, 'happy': 0.3, 'surprise': 5.0, 'sad': 1.5, 'angry': 2.0},
    'exercise': {'neutral': 2.0, 'happy': 3.5, 'surprise': 1.5, 'sad': 0.5, 'angry': 1.5},
    'vlog': {'neutral': 2.5, 'happy': 2.5, 'surprise': 1.5, 'sad': 1.5, 'angry': 1.0},
    'game': {'neutral': 1.5, 'happy': 3.0, 'surprise': 2.5, 'sad': 1.5, 'angry': 2.5},
    'sports': {'neutral': 1.0, 'happy': 3.5, 'surprise': 4.0, 'sad': 1.0, 'angry': 1.5},
    'music': {'neutral': 1.5, 'happy': 4.0, 'surprise': 2.0, 'sad': 2.5, 'angry': 1.0},
    'animal': {'neutral': 1.0, 'happy': 4.5, 'surprise': 3.0, 'sad': 0.8, 'angry': 0.2},
    'beauty': {'neutral': 2.0, 'happy': 3.5, 'surprise': 2.5, 'sad': 0.5, 'angry': 0.5},
    'comedy': {'neutral': 0.2, 'happy': 5.0, 'surprise': 2.0, 'sad': 0.3, 'angry': 0.5},
    'etc': {'neutral': 2.5, 'happy': 2.0, 'surprise': 2.0, 'sad': 1.5, 'angry': 1.5}
}

SCORE_WEIGHTS = {'personalization': 0.40, 'quality': 0.25, 'freshness': 0.15, 'diversity': 0.20}


def cosine_similarity(vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
    emotions = ['neutral', 'happy', 'surprise', 'sad', 'angry']
    v1 = [vec1.get(e, 0.0) for e in emotions]
    v2 = [vec2.get(e, 0.0) for e in emotions]
    dot = sum(a * b for a, b in zip(v1, v2))
    mag1 = math.sqrt(sum(a ** 2 for a in v1))
    mag2 = math.sqrt(sum(b ** 2 for b in v2))
    return dot / (mag1 * mag2) if (mag1 and mag2) else 0.0


def calculate_emotion_preference(watching_data: List[Dict]) -> Dict[str, float]:
    if not watching_data:
        return {'neutral': 0.2, 'happy': 0.2, 'surprise': 0.2, 'sad': 0.2, 'angry': 0.2}
    emotion_sum = {'neutral': 0.0, 'happy': 0.0, 'surprise': 0.0, 'sad': 0.0, 'angry': 0.0}
    for data in watching_data:
        for emotion, pct in data.get('emotion_percentages', {}).items():
            if emotion in emotion_sum:
                emotion_sum[emotion] += pct
    total = sum(emotion_sum.values())
    return {k: v / total for k, v in emotion_sum.items()} if total else {k: 0.2 for k in emotion_sum}


def calculate_personalization_score(video: Dict, favorite_genres: List[str],
                                    emotion_pref: Dict, recent_data: List[Dict]) -> float:
    score = 0.0
    if video.get('category') in favorite_genres:
        idx = favorite_genres.index(video['category'])
        score += [20, 12, 6][min(idx, 2)]
    if recent_data:
        weights = [2.0, 1.8, 1.6, 1.4, 1.2, 1.1, 1.0, 0.9, 0.8, 0.7]
        for i, data in enumerate(recent_data[:10]):
            if i >= len(weights):
                break
            score += (5 if data.get('dominant_emotion') == video.get('dominant_emotion') else 2) * weights[i]
    video_emo = video.get('emotion_distribution', {})
    if video_emo:
        score += cosine_similarity(emotion_pref, video_emo) * 30
    return min(score, 100)


def calculate_quality_score(video: Dict) -> float:
    score = 0.0
    completion = video.get('average_completion_rate', 0.0) * 100
    score += [30, 25, 20, 15, 10, 0][min(int(completion // 10), 5)] if completion >= 50 else 0
    views = video.get('view_count', 0)
    if views > 100:
        score += min(math.log10(views) * 8, 40)
    likes = video.get('like_count', 0)
    if likes > 10:
        score += min(math.log10(likes) * 10, 30)
    return min(score, 100)


def calculate_freshness_score(video: Dict) -> float:
    created = video.get('created_at')
    if not created:
        return 30
    if isinstance(created, str):
        try:
            created = datetime.fromisoformat(created.replace('Z', '+00:00'))
        except:
            return 30
    days = (datetime.utcnow() - created).days
    if days <= 2:
        return 100
    elif days <= 7:
        return 80
    elif days <= 14:
        return 60
    elif days <= 30:
        return 40
    else:
        return max(30 * math.exp(-0.02 * days), 10)


def calculate_diversity_score(video: Dict, cat_dist: Dict, emo_dist: Dict) -> float:
    score = 0.0
    exposure = cat_dist.get(video.get('category'), 0)
    if exposure < 0.05:
        score += 80
    elif exposure < 0.15:
        score += 50
    elif exposure < 0.30:
        score += 20
    emo_exp = emo_dist.get(video.get('dominant_emotion', 'neutral'), 0)
    if emo_exp > 0.6:
        score -= 30
    elif emo_exp < 0.15:
        score += 20
    return max(0, min(score, 100))


def apply_emotion_health(score: float, video: Dict, recent: List[Dict]) -> float:
    if not recent:
        return score
    emo_cnt = {'neutral': 0, 'happy': 0, 'surprise': 0, 'sad': 0, 'angry': 0}
    for d in recent[:15]:
        emo = d.get('dominant_emotion', 'neutral')
        if emo in emo_cnt:
            emo_cnt[emo] += 1
    total = sum(emo_cnt.values())
    if not total:
        return score
    neg_ratio = (emo_cnt['sad'] + emo_cnt['angry']) / total
    v_emo = video.get('dominant_emotion', 'neutral')
    if neg_ratio > 0.35:
        score *= 1.4 if v_emo == 'happy' else (0.6 if v_emo in ['sad', 'angry'] else 1.0)
    if emo_cnt['neutral'] / total > 0.6 and video.get('emotion_distribution', {}).get('neutral', 1.0) < 0.5:
        score *= 1.3
    return score


def get_personalized_recommendations(all_videos: List[Dict], user_data: Dict,
                                     recent_watching: List[Dict], user_logs: List[Dict],
                                     viewed_ids: set, limit: int = 20) -> List[Dict]:
    video_dict = {v['video_id']: v for v in all_videos}
    fav_genres = user_data.get('favorite_genres', [])
    emo_pref = calculate_emotion_preference(recent_watching)
    cat_dist = {}
    for log in user_logs:
        vid = video_dict.get(log.get('video_id'))
        if vid:
            cat = vid.get('category')
            cat_dist[cat] = cat_dist.get(cat, 0) + 1
    total = sum(cat_dist.values())
    if total:
        cat_dist = {k: v/total for k, v in cat_dist.items()}

    scored = []
    for video in all_videos:
        if video['video_id'] in viewed_ids or video.get('is_deleted'):
            continue
        p = calculate_personalization_score(video, fav_genres, emo_pref, recent_watching)
        q = calculate_quality_score(video)
        f = calculate_freshness_score(video)
        d = calculate_diversity_score(video, cat_dist, emo_pref)
        final = p * SCORE_WEIGHTS['personalization'] + q * SCORE_WEIGHTS['quality'] + \
                f * SCORE_WEIGHTS['freshness'] + d * SCORE_WEIGHTS['diversity']
        final = apply_emotion_health(final, video, recent_watching)
        scored.append({'video': video, 'score': final})

    scored.sort(key=lambda x: x['score'], reverse=True)

    result, cats, emos = [], [], []
    for item in scored:
        v = item['video']
        cat, emo = v.get('category'), v.get('dominant_emotion', 'neutral')
        if (len(cats) >= 2 and cats[-2:].count(cat) >= 2) or (len(emos) >= 3 and emos[-3:].count(emo) >= 3):
            continue
        result.append(v)
        cats.append(cat)
        emos.append(emo)
        if len(result) >= limit:
            break
    return result