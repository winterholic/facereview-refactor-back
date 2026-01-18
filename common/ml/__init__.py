"""
ML package
머신러닝 모델 및 관련 유틸리티

- model.h5: 학습된 얼굴 인식 모델
- face_detector: 얼굴 감지 유틸리티
- image_processor: 이미지 전처리
"""

import os

# 모델 경로 (CI/CD 배포 시 덮어씌워지지 않도록 프로젝트 외부 경로 사용)
MODEL_PATH = '/home/winterholic/projects/services/new-facereview-model/model.h5'

# 모델 로딩 함수 (Lazy loading)
def load_model():
    """
    얼굴 인식 모델 로드 (Lazy loading)

    이 함수가 호출될 때만 TensorFlow를 import하여
    앱 시작 시 불필요한 TensorFlow 로딩을 방지합니다.

    Returns:
        Keras model
    """
    from tensorflow import keras

    if os.path.exists(MODEL_PATH):
        return keras.models.load_model(MODEL_PATH)
    else:
        raise FileNotFoundError(f"Model file not found: {MODEL_PATH}")

__all__ = ['load_model', 'MODEL_PATH']
