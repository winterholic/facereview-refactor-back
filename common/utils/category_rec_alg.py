from typing import List, Dict
from common.enum.youtube_genre import GenreEnum

CATEGORY_PREFERRED_EMOTION = {
    GenreEnum.COMEDY: 'happy',
    GenreEnum.DRAMA: 'sad',
    GenreEnum.HORROR: 'surprise',
    GenreEnum.EATING: 'happy',
    GenreEnum.COOK: 'neutral',
    GenreEnum.TRAVEL: 'happy',
    GenreEnum.SHOW: 'surprise',
    GenreEnum.INFORMATION: 'neutral',
    GenreEnum.EXERCISE: 'happy',
    GenreEnum.VLOG: 'neutral',
    GenreEnum.GAME: 'happy',
    GenreEnum.SPORTS: 'surprise',
    GenreEnum.MUSIC: 'happy',
    GenreEnum.ANIMAL: 'happy',
    GenreEnum.BEAUTY: 'neutral',
    GenreEnum.ETC: 'neutral'
}


def get_top_videos_by_category_emotion(
    videos_by_category: Dict[str, List[Dict]],
    limit: int = 20
) -> Dict[str, List[Dict]]:

    result = {}

    for category_name, videos in videos_by_category.items():
        if not videos:
            result[category_name] = []
            continue

        if not videos:
            result[category_name] = []
            continue

        category = videos[0].get('category')
        preferred_emotion = CATEGORY_PREFERRED_EMOTION.get(category, 'neutral')

        videos_with_emotion_ratio = []
        for video in videos:
            emotion_dist = video.get('emotion_distribution', {})

            if not emotion_dist or sum(emotion_dist.values()) == 0:
                continue

            emotion_ratio = emotion_dist.get(preferred_emotion, 0.0)

            video_with_ratio = video.copy()
            video_with_ratio['preferred_emotion_ratio'] = emotion_ratio
            videos_with_emotion_ratio.append(video_with_ratio)

        sorted_videos = sorted(
            videos_with_emotion_ratio,
            key=lambda x: x['preferred_emotion_ratio'],
            reverse=True
        )
        result[category_name] = sorted_videos[:limit]

    return result
