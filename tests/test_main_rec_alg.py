import unittest

from common.utils.main_rec_alg import _generate_candidate_videos


class MainRecommendationAlgorithmTest(unittest.TestCase):
    def test_generate_candidate_videos_limits_ranking_pool_and_prefers_emotion_match(self):
        videos = []
        for i in range(260):
            emotion = 'happy' if i == 259 else 'sad'
            videos.append({
                'video_id': f'video-{i}',
                'category': 'music',
                'dominant_emotion': emotion,
                'emotion_distribution': {
                    'neutral': 0.0,
                    'happy': 1.0 if emotion == 'happy' else 0.0,
                    'surprise': 0.0,
                    'sad': 0.0 if emotion == 'happy' else 1.0,
                    'angry': 0.0,
                },
                'average_completion_rate': 0.5,
                'view_count': 100,
                'like_count': 20,
                'created_at': None,
                'is_deleted': False,
            })

        candidates = _generate_candidate_videos(
            all_videos=videos,
            viewed_ids=set(),
            favorite_genres=['music'],
            emotion_pref={'neutral': 0.0, 'happy': 1.0, 'surprise': 0.0, 'sad': 0.0, 'angry': 0.0},
            user_logs=[],
            limit=20,
        )

        self.assertLessEqual(len(candidates), 200)
        self.assertEqual(candidates[0]['video_id'], 'video-259')


if __name__ == '__main__':
    unittest.main()
