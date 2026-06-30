import unittest

from common.utils.main_rec_alg import (
    _generate_candidate_videos,
    calculate_emotion_preference,
    get_personalized_recommendations,
)


class MainRecommendationAlgorithmTest(unittest.TestCase):
    def test_emotion_preference_weights_recent_watching_more_than_old_watching(self):
        preference = calculate_emotion_preference([
            {
                'dominant_emotion': 'happy',
                'emotion_percentages': {
                    'neutral': 0.0,
                    'happy': 1.0,
                    'surprise': 0.0,
                    'sad': 0.0,
                    'angry': 0.0,
                },
            },
            {
                'dominant_emotion': 'sad',
                'emotion_percentages': {
                    'neutral': 0.0,
                    'happy': 0.0,
                    'surprise': 0.0,
                    'sad': 1.0,
                    'angry': 0.0,
                },
            },
        ])

        self.assertGreater(preference['happy'], preference['sad'])

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

    def test_recommendations_keep_emotion_relevance_without_over_repeating_categories(self):
        videos = []
        for i in range(10):
            category = 'music' if i < 6 else 'sports'
            emotion = 'happy' if i % 2 == 0 else 'sad'
            videos.append({
                'video_id': f'video-{i}',
                'category': category,
                'dominant_emotion': emotion,
                'emotion_distribution': {
                    'neutral': 0.0,
                    'happy': 0.8 if emotion == 'happy' else 0.1,
                    'surprise': 0.1,
                    'sad': 0.1 if emotion == 'happy' else 0.8,
                    'angry': 0.0,
                },
                'average_completion_rate': 0.8,
                'view_count': 1000,
                'like_count': 100,
                'created_at': None,
                'is_deleted': False,
            })

        result = get_personalized_recommendations(
            all_videos=videos,
            user_data={'favorite_genres': ['music', 'sports']},
            recent_watching=[
                {
                    'video_id': 'old-1',
                    'category': 'music',
                    'dominant_emotion': 'happy',
                    'emotion_percentages': {
                        'neutral': 0.0,
                        'happy': 0.8,
                        'surprise': 0.1,
                        'sad': 0.1,
                        'angry': 0.0,
                    },
                }
            ],
            user_logs=[],
            viewed_ids=set(),
            limit=4,
        )

        self.assertEqual(len(result), 4)
        self.assertIn('sports', {video['category'] for video in result})
        self.assertGreaterEqual(
            sum(1 for video in result if video['dominant_emotion'] == 'happy'),
            2
        )

    def test_recommendations_fill_limit_even_when_top_scores_are_same_category(self):
        videos = []
        for i in range(40):
            videos.append({
                'video_id': f'music-{i}',
                'category': 'music',
                'dominant_emotion': 'happy',
                'emotion_distribution': {
                    'neutral': 0.0,
                    'happy': 1.0,
                    'surprise': 0.0,
                    'sad': 0.0,
                    'angry': 0.0,
                },
                'average_completion_rate': 1.0,
                'view_count': 5000,
                'like_count': 500,
                'created_at': None,
                'is_deleted': False,
            })
        for i in range(10):
            videos.append({
                'video_id': f'sports-{i}',
                'category': 'sports',
                'dominant_emotion': 'surprise',
                'emotion_distribution': {
                    'neutral': 0.0,
                    'happy': 0.3,
                    'surprise': 0.7,
                    'sad': 0.0,
                    'angry': 0.0,
                },
                'average_completion_rate': 0.6,
                'view_count': 50,
                'like_count': 5,
                'created_at': None,
                'is_deleted': False,
            })

        result = get_personalized_recommendations(
            all_videos=videos,
            user_data={'favorite_genres': ['music']},
            recent_watching=[
                {
                    'category': 'music',
                    'dominant_emotion': 'happy',
                    'emotion_percentages': {
                        'neutral': 0.0,
                        'happy': 1.0,
                        'surprise': 0.0,
                        'sad': 0.0,
                        'angry': 0.0,
                    },
                }
            ],
            user_logs=[],
            viewed_ids=set(),
            limit=5,
        )

        self.assertEqual(len(result), 5)


if __name__ == '__main__':
    unittest.main()
