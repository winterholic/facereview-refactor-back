import os

MODEL_PATH = os.path.join(os.path.dirname(__file__), 'model.h5')

def load_model():
    #NOTE: TensorFlow import를 호출 시점까지 미뤄 웹 프로세스 시작 비용을 줄인다.
    from tensorflow import keras

    if os.path.exists(MODEL_PATH):
        return keras.models.load_model(MODEL_PATH)
    raise FileNotFoundError(f"Model file not found: {MODEL_PATH}")

__all__ = ['load_model', 'MODEL_PATH']
