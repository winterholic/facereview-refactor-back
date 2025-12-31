from flask import Flask, url_for, request, jsonify, abort, Blueprint, current_app, session, g, make_response
from datetime import datetime, timedelta
import bcrypt
from pymongo import MongoClient
import jwt
import re
import random
from jwtfunction import decode_token, create_access_token, create_refresh_token, create_tmp_token

#blueprint연결
gate_blueprint = Blueprint("gate", __name__, url_prefix='/gate')


# MongoDB 연결 설정
client = MongoClient('mongodb://localhost:27017/')
db = client.FaceReview_Database
collection_user = db.user
collection_profile = db.user_profile


#유저 확인
def authenticate(email_id, password):
    user_filter_query = {'user_email_id': email_id, 'user_activate' : 7} #유저 아이디로 유저가 있는지 검색
    user_document = collection_user.find_one(user_filter_query)

    if user_document : #유저가 있다면
        user = {
            'index': user_document['user_index'], #index
            'email_id': user_document['user_email_id'], #id
            'user_name' : user_document['user_name'],
            'user_profile' : user_document['user_profile'],
            'user_tutorial' : user_document['user_tutorial'],
            'check_time' : datetime.utcnow(),
            'user_role' : user_document['user_role'],
            'user_favorite_genre_1' : user_document['user_favorite_genre_1'],
            'user_favorite_genre_2' : user_document['user_favorite_genre_2'],
            'user_favorite_genre_3' : user_document['user_favorite_genre_3'],
            'user_index' : user_document['user_index']
        }
        if bcrypt.checkpw(password.encode('utf-8'), user_document['user_pw'].encode('utf-8')): #비밀번호가 일치하다면
            return user
        else : #비밀번호가 일치하지 않는다면
            return None
    else : #유저가 없다면
        return None

# 유저가 로그인 시 리프레시 토큰, 엑세스 토큰 새로 발급
# 엑세스 유효 검사해서 유효하면, 유효한지만 알려주고 유효하지 않으면 400
# 리프레시 유효 검사해서 유효하면, 리프레시와 엑세스 새로 발급해주고 유효하지 않으면 400


@gate_blueprint.route('email-verify', methods = ['GET', 'POST'])
def email_verify():
    data = request.get_json()
    email_id = data.get('email_id', None)

    user_document = collection_user.find_one({'user_email_id' : email_id, 'user_activate' : 7})

    if user_document :
        return jsonify({'message': 'user is exist'}), 200
    else :
        return jsonify({'message': 'Invalid email'}), 201


# 로그인기능, /gate/login로 라우팅
@gate_blueprint.route('login', methods = ['GET', 'POST'])
def login():
    data = request.get_json()
    email_id = data.get('email_id', None)
    password = data.get('password', None)
    
    if password is None: #pw를 입력하지 않은경우 400
        return jsonify({'message': 'password is required.'}), 400

    user = authenticate(email_id, password)

    if user: # id가 존재하고 pw가 일치하는 경우
        access_token = create_access_token(email_id)
        refresh_token = create_refresh_token(email_id)
        
        #print("login : access token : ", access_token)
        #print("login : refresh token : ", refresh_token)

        user_name = user['user_name']
        user_profile = user['user_profile']
        user_tutorial = user['user_tutorial']
        user_role = user['user_role']
        user_favorite_genre_1 = user['user_favorite_genre_1']
        user_favorite_genre_2 = user['user_favorite_genre_2']
        user_favorite_genre_3 = user['user_favorite_genre_3']
        user_index = user['user_index']
        
        login_dict = {
            'message': 'Successful login',
            'access_token' : access_token,
            'refresh_token' : refresh_token,
            'user_name' : user_name,
            'user_profile' : user_profile,
            'user_tutorial' : user_tutorial,
            'user_role' : user_role,
            'user_favorite_genre_1' : user_favorite_genre_1,
            'user_favorite_genre_2' : user_favorite_genre_2,
            'user_favorite_genre_3' : user_favorite_genre_3,
            'user_index' : user_index
        }

        return jsonify(login_dict), 200

    if user is None: # id가 존재하지만 해당 id와 pw가 일치하는 id가 아닌 경우
        return jsonify({'message': 'Invalid credentials'}), 401


def token_verification(token):
    if decode_token(token) is None : 
        return 'wrong token'
    decoded_token = decode_token(token)
    #decoded_token에는 id, ist, exp, type이 있고
    #id에는 유저의 id ist에는 토큰 발급시간 exp에는 만료기간 type에는 토큰의 타입이 들어가 있고 형태는 'access'혹은 'refresh'이다.

    curr_time = datetime.utcnow() #현재 시간
    str_exp_time = decoded_token['expir'] #만료 기간
    exp_time = datetime.strptime(str_exp_time, "%Y-%m-%dT%H:%M:%S.%f") #문자열에서 다시 datetime객체로 변형

    if curr_time > exp_time: #현재시간 > 만료기간 , 즉 만료된 경우
        return 'expired token'
    
    if collection_user.find_one({'user_email_id': decoded_token['id'], 'user_activate' : 7}) is None:
        return 'non-existent user'
    
    return 'valid token'
    

#액세스 토큰 유효 검사 , /gate/access-verify로 라우팅
@gate_blueprint.route('access-verify', methods = ['GET', 'POST'])
def access_Verification():
    cur_access_token = request.headers.get('Authorization')
    
    verification_result = token_verification(cur_access_token)

    if verification_result == 'wrong token' :
        return jsonify({'message': 'This access token is Wrong'}), 408
    
    elif verification_result == 'expired token' :
        return jsonify({'message': 'This access token is expired'}), 408

    elif verification_result == 'non-existent user' :
        return jsonify({'message': 'User does not exist'}), 409

    elif verification_result == 'valid token' :
        return jsonify({'message': 'This access token is effective'}), 200
    

#리프레시 토큰 유효 검사, /gate/refresh-verify로 라우팅
@gate_blueprint.route('refresh-verify', methods = ['GET', 'POST'])
def refresh_Verification():
    cur_refresh_token = request.headers.get('Authorization')
    
    verification_result = token_verification(cur_refresh_token)

    if verification_result == 'wrong token' :
        return jsonify({'message': 'This refresh token is Wrong'}), 408
    
    elif verification_result == 'expired token' :
        return jsonify({'message': 'This refresh token is expired'}), 408

    elif verification_result == 'non-existent user' :
        return jsonify({'message': 'User does not exist'}), 409
    
    elif verification_result == 'valid token' :
        decoded_token = decode_token(cur_refresh_token) # token을 decode
        email_id = decoded_token['id'] #id를 가져와서 새로운 토큰을 발급

        access_token = create_access_token(email_id) #액세스 토큰 발급
        refresh_token = create_refresh_token(email_id) #리프레시 토큰 발급

        return jsonify({'message': 'refresh token is effective', 'access_token' : access_token, 'refresh_token' : refresh_token}), 200
    

#회원가입기능, /gate/signup로 라우팅
@gate_blueprint.route('signup', methods = ['GET', 'POST'])
def signup():
    data = request.get_json()
    user_email_id = data.get('email_id', None)
    password = data.get('password', None)
    user_name = data.get('user_name', None)
    user_favorite_genre_1 = data.get('user_favorite_genre_1', None)
    user_favorite_genre_2 = data.get('user_favorite_genre_2', None)
    user_favorite_genre_3 = data.get('user_favorite_genre_3', None)

    # 이메일(ID) 중복 확인, 400
    if collection_user.find_one({'user_email_id': user_email_id, 'user_activate' : 7}):
        return jsonify({'message': 'Email (ID) already in use'}), 400
    
    # 비밀번호 형식 검사 (8자 이상, 64자이하, 숫자 포함)
    if not re.match(r'^(?=.*\d)(?=.*[a-zA-Z]).{8,64}$', password):
        return jsonify({'message': 'Password must be at least 8 characters and must contain numbers.'}), 400
    
    # 닉네임 형식 검사
    if not re.match(r'^.{2,10}$', user_name):
        return jsonify({'message': 'Nickname must be between 2 and 10 characters.'}), 400

    pw_encrypted = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()) #암호화
    decoded_pw = pw_encrypted.decode('utf-8') #해시 문자 변환

    document_count = collection_user.count_documents({})
    index_max_value = document_count + 1

    collection_user.insert_one({
        "user_index": index_max_value,
        "user_email_id": user_email_id,
        "user_pw": decoded_pw,
        "user_name": user_name,
        "user_favorite_genre_1": user_favorite_genre_1,
        "user_favorite_genre_2": user_favorite_genre_2,
        "user_favorite_genre_3": user_favorite_genre_3,
        "user_create_time" : datetime.utcnow(),
        "user_role": 1, # user_role 1 일반 유저, user_role 2 관리자
        "user_point": 0,
        "user_profile" : 0,
        "user_tutorial" : 0,
        "user_activate" : 7 # user_activate 7 활성화, user_activate 0 비활성화
    })
    
    return jsonify({'message': 'Successful registration'}), 200


# 튜토리얼 여부 확인, /gate/before-tutorial로 라우팅
@gate_blueprint.route('before-tutorial', methods = ['GET', 'POST'])
def before_tutorial():
    data = request.get_json()
    user_access_token = request.headers.get('Authorization')
    #print('토큰 :', user_access_token)

    verification_result = token_verification(user_access_token)

    if verification_result == 'wrong token' :
        return jsonify({'message': 'This access token is Wrong'}), 408
    
    elif verification_result == 'expired token' :
        return jsonify({'message': 'This access token is expired'}), 408

    elif verification_result == 'non-existent user' :
        return jsonify({'message': 'User does not exist'}), 409

    elif verification_result == 'valid token' :
        user_decoded_token = decode_token(user_access_token)
        email_id = user_decoded_token['id']

        user_document = collection_user.find_one({'user_email_id': email_id, 'user_activate' : 7})
        user_tutorial = user_document['user_tutorial']

        # user_tutorial 2회까지 가능, 2회 이상이면 user_tutorial 수행하지 않음
        if user_tutorial > 1 :
            return jsonify({'message' : 'Tutorial is not required for this user.', 'user_tutorial' : user_tutorial}), 200
        else :
            return jsonify({'message' : 'Tutorial is required for this user', 'user_tutorial' : user_tutorial }), 200

    
# 튜토리얼 후 DB수정, /gate/after-tutorial로 라우팅
@gate_blueprint.route('after-tutorial', methods = ['GET', 'POST'])
def after_tutorial():
    user_access_token = request.headers.get('Authorization')

    verification_result = token_verification(user_access_token)

    if verification_result == 'wrong token' :
        return jsonify({'message': 'This access token is Wrong'}), 408
    
    elif verification_result == 'expired token' :
        return jsonify({'message': 'This access token is expired'}), 408

    elif verification_result == 'non-existent user' :
        return jsonify({'message': 'User does not exist'}), 409

    elif verification_result == 'valid token' :
        user_decoded_token = decode_token(user_access_token)
        email_id = user_decoded_token['id']

        tutorial_filter_query = {'user_email_id' : email_id}
        tutorial_update_query = {'$inc': {'user_tutorial': +1}} #{'$set': {'user_tutorial': 1}}
        result = collection_user.update_one(tutorial_filter_query, tutorial_update_query)

        return jsonify({'message' : 'Updated tutorial data'}), 200
    

# 비로그인 유저 임시토큰 발급, /gate/temp-token로 라우팅
@gate_blueprint.route('temp-token', methods = ['GET', 'POST'])
def temp_token_issuance():
    new_temp_token = create_tmp_token()

    return jsonify({'message': 'Temporary token has been successfully issued', 'new_temp_token':new_temp_token})