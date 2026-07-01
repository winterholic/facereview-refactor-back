import unittest

from common.utils.recommendation_alg import (
    compute_base_score,
    emotion_cosine,
    build_user_emotion_profile,
    rank_personalized,
)


def _stats(neutral, peak_emotion, peak_val, completion, frames, views=1000, likes=100):
    dist = {'neutral': neutral, 'happy': 0.0, 'surprise': 0.0, 'sad': 0.0, 'angry': 0.0}
    dist[peak_emotion] = peak_val
    return {
        'emotion_distribution': dist,
        'average_completion_rate': completion,
        'sample_frames': frames,
        'view_count': views,
        'like_count': likes,
        'created_at': None,
    }


class BaseScoreTest(unittest.TestCase):
    def test_engaging_video_beats_flat_neutral_video(self):
        engaging = _stats(neutral=0.2, peak_emotion='surprise', peak_val=0.6, completion=0.9, frames=2000)
        flat = _stats(neutral=0.95, peak_emotion='surprise', peak_val=0.03, completion=0.3, frames=2000)
        self.assertGreater(compute_base_score(engaging), compute_base_score(flat))

    def test_low_sample_is_penalized_by_confidence(self):
        #NOTE: 동일 감정/완주율이라도 표본이 적으면 base_score가 낮아야 함 (상위 독점 방지)
        well_sampled = _stats(neutral=0.2, peak_emotion='happy', peak_val=0.6, completion=0.9, frames=5000)
        under_sampled = _stats(neutral=0.2, peak_emotion='happy', peak_val=0.6, completion=0.9, frames=20)
        self.assertGreater(compute_base_score(well_sampled), compute_base_score(under_sampled))

    def test_score_bounded(self):
        maxed = _stats(neutral=0.0, peak_emotion='happy', peak_val=1.0, completion=1.0,
                       frames=1_000_000, views=10_000_000, likes=1_000_000)
        self.assertLessEqual(compute_base_score(maxed), 100.0)
        self.assertGreaterEqual(compute_base_score(maxed), 0.0)


class CosineTest(unittest.TestCase):
    def test_identical_vectors(self):
        v = {'neutral': 0.1, 'happy': 0.2, 'surprise': 0.4, 'sad': 0.2, 'angry': 0.1}
        self.assertAlmostEqual(emotion_cosine(v, v), 1.0, places=6)

    def test_empty_vector(self):
        self.assertEqual(emotion_cosine({}, {'happy': 1.0}), 0.0)


class UserProfileTest(unittest.TestCase):
    def test_recent_emotion_dominates_profile(self):
        recent = [
            {'emotion_percentages': {'surprise': 0.8, 'neutral': 0.2}},
            {'emotion_percentages': {'surprise': 0.7, 'neutral': 0.3}},
        ]
        profile = build_user_emotion_profile(recent)
        self.assertEqual(max(profile, key=profile.get), 'surprise')

    def test_cold_start_profile_non_neutral(self):
        profile = build_user_emotion_profile([])
        self.assertEqual(profile['neutral'], 0.0)


class RankPersonalizedTest(unittest.TestCase):
    def _pool(self):
        #NOTE: base_score 내림차순 풀. 대표감정을 섞어 개인화 재정렬 검증
        pool = []
        for i in range(200):
            emo = 'surprise' if i % 2 == 0 else 'happy'
            dist = {'neutral': 0.2, 'happy': 0.0, 'surprise': 0.0, 'sad': 0.0, 'angry': 0.0}
            dist[emo] = 0.6
            pool.append({
                'video_id': f'v{i}', 'youtube_url': f'u{i}', 'title': f't{i}',
                'category': 'horror' if emo == 'surprise' else 'comedy',
                'dominant_emotion': emo, 'dominant_emotion_per': 60.0,
                'emotion_distribution': dist, 'base_score': 100.0 - i * 0.1,
            })
        return pool

    def test_returns_limit_and_excludes_viewed(self):
        pool = self._pool()
        viewed = {'v0', 'v2', 'v4'}
        result = rank_personalized(pool, [], [], viewed, limit=20)
        self.assertEqual(len(result), 20)
        ids = {v['video_id'] for v in result}
        self.assertTrue(viewed.isdisjoint(ids))

    def test_horror_lover_gets_more_surprise_videos(self):
        #NOTE: 공포(=surprise)를 계속 본 유저에게 surprise 대표 영상이 더 많이 추천되어야 함
        pool = self._pool()
        horror_recent = [{'emotion_percentages': {'surprise': 0.8, 'neutral': 0.2},
                          'dominant_emotion': 'surprise', 'category': 'horror'} for _ in range(5)]
        personalized = rank_personalized(pool, horror_recent, [], set(), limit=20)
        neutral_user = rank_personalized(pool, [], [], set(), limit=20)
        surprise_personal = sum(1 for v in personalized if v['dominant_emotion'] == 'surprise')
        surprise_neutral = sum(1 for v in neutral_user if v['dominant_emotion'] == 'surprise')
        self.assertGreater(surprise_personal, surprise_neutral)

    def test_empty_pool_returns_empty(self):
        self.assertEqual(rank_personalized([], [], [], set(), limit=20), [])


if __name__ == '__main__':
    unittest.main()
