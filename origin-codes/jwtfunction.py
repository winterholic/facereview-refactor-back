import jwt
from datetime import datetime, timedelta
from jwt.exceptions import DecodeError, InvalidSignatureError, InvalidAlgorithmError
import random
import string

#jwt 구현 메소드
access_expires = timedelta(days=7) # 토큰의 만료 시간 = 1시간
refresh_expires = timedelta(days=7)  # 토큰의 만료 시간 = 7일
access_type = 'access'
refresh_type = 'refresh'


def encode_token(email_id, expires, token_type) :
    # 현재 시간을 UTC 기준으로 얻기
    current_utc_time = datetime.utcnow()
    expiration_utc_time = current_utc_time + expires

    # UTC 시간을 문자열로 변환
    formatted_utc_time = current_utc_time.isoformat()

    # UTC 시간을 문자열로 변환
    formatted_exp_utc_time = expiration_utc_time.isoformat()

    payload = {
        "id" : email_id, #유저 ID
        "ist" : formatted_utc_time, # 토큰 발급시간
        "expir" : formatted_exp_utc_time, # 만료기간
        "type" : token_type #토큰 type
    }
    encoded_token = jwt.encode(payload, "capstonekey", algorithm="HS256") # 키 : capstonekey
    return encoded_token

def decode_token(encoded_token) :
    #print('trying_this_token : ', encoded_token)
    try : 
        decoded_token = jwt.decode(encoded_token, "capstonekey", algorithms=["HS256"])
    except DecodeError as e:
    # 토큰 디코드 오류 처리
        print(f"토큰 디코드 오류: {e}")
        return None
    except InvalidSignatureError as e:
    # 서명이 올바르지 않은 경우 처리
        print(f"서명 오류: {e}")
        return None
    except InvalidAlgorithmError as e:
    # 알고리즘이 허용되지 않는 경우 처리
        print(f"알고리즘 오류: {e}")
        return None
    
    return decoded_token 

def create_access_token(email_id) :
    new_access_token = encode_token(email_id, access_expires, access_type)
    return new_access_token

def create_refresh_token(email_id) :
    new_refresh_token = encode_token(email_id, access_expires, refresh_type)
    return new_refresh_token

def generate_random_string(length):
    alphabet = string.ascii_letters + string.digits
    random_string = ''.join(random.choice(alphabet) for _ in range(length))
    return random_string

def create_tmp_token():
    expires = timedelta(days=1)
    # 현재 시간을 UTC 기준으로 얻기
    current_utc_time = datetime.utcnow()
    expiration_utc_time = current_utc_time + expires

    # UTC 시간을 문자열로 변환
    formatted_utc_time = current_utc_time.isoformat()

    # UTC 시간을 문자열로 변환
    formatted_exp_utc_time = expiration_utc_time.isoformat()

    # 랜덤 문자열 생성
    random_string_40 = generate_random_string(40)

    payload = {
        "id" : random_string_40,
        "ist" : formatted_utc_time, # 토큰 발급시간
        "expir" : formatted_exp_utc_time, # 만료기간
        "type" : 'guest'
    }

    encoded_token = jwt.encode(payload, "capstonekey", algorithm="HS256")
    #print('tmp_token : ', encoded_token)
    return encoded_token