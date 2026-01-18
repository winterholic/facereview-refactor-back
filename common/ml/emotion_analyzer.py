import os
import base64
import io
import numpy as np
import cv2
import cvlib as cv
from PIL import Image
from typing import Dict, Tuple
from common.utils.logging_utils import get_logger

logger = get_logger('emotion_analyzer')


class EmotionAnalyzer:
    _instance = None
    _model = None

    EMOTIONS = ["happy", "surprise", "angry", "sad", "neutral"]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._model is None:
            self._load_model()

    def _load_model(self):
        #NOTE: TensorFlow import를 이 시점에만 수행하여 앱 시작 속도 개선
        from tensorflow import keras
        from common.ml import MODEL_PATH

        self._model = keras.models.load_model(MODEL_PATH)
        logger.info(f"Model loaded from {MODEL_PATH}")

    def analyze_emotion(self, base64_frame_data: str) -> Dict[str, float]:
        try:
            imgdata = base64.b64decode(base64_frame_data)
            image = Image.open(io.BytesIO(imgdata))
            image = np.array(image)

            faces, conf = cv.detect_face(image)

            if len(faces) == 0:
                return self._get_default_emotion()

            x, y, x2, y2 = faces[0]
            cropped_image = image[y:y2, x:x2]

            resized_face = cv2.resize(cropped_image, (96, 96))
            gray_face = cv2.cvtColor(resized_face, cv2.COLOR_BGR2GRAY)

            img = gray_face / 255.0
            img = img.reshape(96, 96, 1)
            img = np.expand_dims(img, axis=0)

            pred = self._model.predict(img, verbose=0)

            emotion_percentages = [round(x * 100, 2) for x in pred[0]]

            emotion_dict = {
                'happy': emotion_percentages[0],
                'surprise': emotion_percentages[1],
                'angry': emotion_percentages[2],
                'sad': emotion_percentages[3],
                'neutral': emotion_percentages[4]
            }

            most_emotion = max(emotion_dict, key=emotion_dict.get)
            emotion_dict['most_emotion'] = most_emotion

            return emotion_dict

        except Exception as e:
            logger.error(f"Error during emotion analysis: {e}")
            return self._get_default_emotion()

    def _get_default_emotion(self) -> Dict[str, float]:
        return {
            'happy': 0.0,
            'surprise': 0.0,
            'angry': 0.0,
            'sad': 0.0,
            'neutral': 100.0,
            'most_emotion': 'neutral'
        }
