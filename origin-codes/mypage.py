# -*- coding: utf-8 -*-
import xml.etree.ElementTree as elemTree
#from flask import *
#from flask_jwt import *
from flask import Flask, url_for, request, jsonify, abort, Blueprint, current_app, session, g
from datetime import datetime, timedelta
from pymongo import MongoClient
import bcrypt
import re
from typing import Union
from gate import token_verification
from jwtfunction import decode_token, create_access_token, create_refresh_token


mypage_blueprint = Blueprint("mypage", __name__, url_prefix='/mypage')


#Parse XML
tree = elemTree.parse('keys.xml')
secretkey = tree.find('string[@name="secret_key"]').text
app = Flask(__name__)
app.config['SECRET_KEY'] = secretkey

# MongoDB 연결 설정
client = MongoClient('mongodb://localhost:27017/')
db = client.FaceReview_Database
collection_user = db.user
collection_youtube_video = db.youtube_video
collection_video_distribution = db.video_distribution
collection_user_profile = db.user_profile
collection_youtube_watching_data = db.youtube_watching_data
collection_youtube_watching_timeline = db.youtube_watching_timeline
collection_youtube_watching_timeline_data = db.youtube_watching_timeline_data


#emotion_score측정
def choise_emotion_per(this_emotion, neutral_statistics_per, happy_statistics_per, surprise_statistics_per, sad_statistics_per, angry_statistics_per) :
    if this_emotion == 'neutral' :
        emotion_per = neutral_statistics_per
    elif this_emotion == 'happy' :
        emotion_per = happy_statistics_per
    elif this_emotion == 'surprise' :
        emotion_per = surprise_statistics_per
    elif this_emotion == 'sad' :
        emotion_per = sad_statistics_per
    elif this_emotion == 'angry' :
        emotion_per = angry_statistics_per
    elif this_emotion == 'None' :
        emotion_per = float(0)
    return emotion_per


#최근 영상목록 생성 메소드
def make_recent_list(email_id):
    user_filter_query = {'user_email_id': email_id, 'user_activate' : 7} #userid로 user찾는 필터쿼리 user_filter_query
    user_document = collection_user.find_one(user_filter_query)
    user_index = user_document['user_index']

    recent_video_filter_query = {'user_index': user_index, 'watching_data_activate' : 7} #userid로 유저시청기록 찾는 쿼리
    recent_video_documents = collection_youtube_watching_data.find(recent_video_filter_query).sort({'watching_data_index': -1}) #해당 유저의 모든 시청(감정분석기록) 검색

    recent_video_lists = [] #필요한 데이터들을 저장할 list

    for recent_video_document in recent_video_documents :
        youtube_index = recent_video_document['youtube_index']
        most_emotion = recent_video_document['most_emotion']
        data_create_time = recent_video_document['data_create_time']
        this_watching_data_index = recent_video_document['watching_data_index']

        neutral_statistics_per = recent_video_document['emotion_statistics_per']['neutral']
        happy_statistics_per = recent_video_document['emotion_statistics_per']['happy']
        surprise_statistics_per = recent_video_document['emotion_statistics_per']['surprise']
        sad_statistics_per = recent_video_document['emotion_statistics_per']['sad']
        angry_statistics_per = recent_video_document['emotion_statistics_per']['angry']

        most_emotion_per = choise_emotion_per(most_emotion, neutral_statistics_per, happy_statistics_per, surprise_statistics_per, sad_statistics_per, angry_statistics_per)

        youtube_filter_query = {'youtube_index' : youtube_index, 'youtube_activate' : 7}
        youtube_document = collection_youtube_video.find_one(youtube_filter_query)
        youtube_title = youtube_document['youtube_title']
        youtube_url = youtube_document['youtube_url']

        flag = 1
        for recent_video_list in recent_video_lists :
            check_youtube_url = recent_video_list['youtube_url']
            if youtube_url == check_youtube_url :
                flag = 0
                break
        if flag == 1 :
            recent_video_dict = {
                'youtube_title' : youtube_title,
                'youtube_url' : youtube_url,
                'most_emotion' : most_emotion,
                'most_emotion_per' : round(most_emotion_per * 100, 2),
                'date_create_time' : data_create_time
            }

            youtube_filter_query = {'youtube_url' : youtube_url, 'youtube_activate' : 7}
            this_youtube_document = collection_youtube_video.find_one(youtube_filter_query)

            youtube_length_hour = this_youtube_document['youtube_length_hour']
            youtube_length_minute = this_youtube_document['youtube_length_minute']
            youtube_length_second = this_youtube_document['youtube_length_second']

            timeline_dict = {}

            # 시작 시간
            start_time = timedelta(seconds=1)

            # 종료 시간
            end_time = timedelta(hours=youtube_length_hour, minutes=youtube_length_minute, seconds=youtube_length_second)

            # 시간 간격
            time_interval = timedelta(seconds=1)

            #print(timeline_document)

            timeline_data_filter_query = {'watching_data_index' : this_watching_data_index, 'watching_timeline_activate' : 7}
            timeline_data_document = collection_youtube_watching_timeline_data.find_one(timeline_data_filter_query)
            #print(timeline_data_document)

            happy_list = []
            neutral_list = []
            angry_list = []
            sad_list = []
            surprise_list = []

            distribution_dict = {}

            data_num = 0

            while start_time <= end_time:
                formatted_time = str(start_time)[0:10] #시간데이터 문자열 변환 00:00:00과같은 형식

                #데이터 불러오기
                happy_per = timeline_data_document[formatted_time]['happy']
                neutral_per = timeline_data_document[formatted_time]['neutral']
                angry_per = timeline_data_document[formatted_time]['angry']
                sad_per = timeline_data_document[formatted_time]['sad']
                surprise_per = timeline_data_document[formatted_time]['surprise']

                dict1 = {
                    'x' : formatted_time,
                    'y' : happy_per
                }

                dict2 = {
                    'x' : formatted_time,
                    'y' : neutral_per
                }

                dict3 = {
                    'x' : formatted_time,
                    'y' : angry_per
                }

                dict4 = {
                    'x' : formatted_time,
                    'y' : sad_per
                }

                dict5 = {
                    'x' : formatted_time,
                    'y' : surprise_per
                }   

                happy_list.append(dict1)
                neutral_list.append(dict2)
                angry_list.append(dict3)
                sad_list.append(dict4)
                surprise_list.append(dict5)

                data_num += 1
                
                start_time += time_interval

            new_happy_list = []
            new_neutral_list = []
            new_angry_list = []
            new_sad_list = []
            new_surprise_list = []

            tmp_num = data_num / 40
            Parameter = round(tmp_num, 0)

            if data_num > 40 :
                temp_sum = 0
                temp_index = 1
                index = 0
                for happy_dict in happy_list :
                    #print(happy_dict)
                    if(index % Parameter == 0 and index != 0) :
                        temp_data = round(temp_sum / Parameter, 1)
                        temp_dict = {
                            'x' : temp_index,
                            'y' : temp_data
                        }
                        new_happy_list.append(temp_dict)
                        temp_sum = 0
                        temp_index += 1
                        index += 1
                    else :
                        temp_sum += happy_dict['y']
                        index += 1
                temp_sum = 0
                temp_index = 1
                index = 0
                for neutral_dict in neutral_list :
                    if(index % Parameter == 0 and index != 0) :
                        temp_data = round(temp_sum / Parameter, 1)
                        temp_dict = {
                            'x' : temp_index,
                            'y' : temp_data
                        }
                        new_neutral_list.append(temp_dict)
                        temp_sum = 0
                        temp_index += 1
                        index += 1
                    else :
                        temp_sum += neutral_dict['y']
                        index += 1
                temp_sum = 0
                temp_index = 1
                index = 0
                for angry_dict in angry_list :
                    if(index % Parameter == 0 and index != 0) :
                        temp_data = round(temp_sum / Parameter, 1)
                        temp_dict = {
                            'x' : temp_index,
                            'y' : temp_data
                        }
                        new_angry_list.append(temp_dict)
                        temp_sum = 0
                        temp_index += 1
                        index += 1
                    else :
                        temp_sum += angry_dict['y']
                        index += 1
                temp_sum = 0
                temp_index = 1
                index = 0
                for sad_dict in sad_list :
                    if(index % Parameter == 0 and index != 0) :
                        temp_data = round(temp_sum / Parameter, 1)
                        temp_dict = {
                            'x' : temp_index,
                            'y' : temp_data
                        }
                        new_sad_list.append(temp_dict)
                        temp_sum = 0
                        temp_index += 1
                        index += 1
                    else :
                        temp_sum += sad_dict['y']
                        index += 1
                temp_sum = 0
                temp_index = 1
                index = 0
                for surprise_dict in surprise_list :
                    if(index % Parameter == 0 and index != 0) :
                        temp_data = round(temp_sum / Parameter, 1)
                        temp_dict = {
                            'x' : temp_index,
                            'y' : temp_data
                        }
                        new_surprise_list.append(temp_dict)
                        temp_sum = 0
                        temp_index += 1
                        index += 1
                    else :
                        temp_sum += surprise_dict['y']
                        index += 1
            else :
                new_happy_list = happy_list
                new_neutral_list = neutral_list
                new_angry_list = angry_list
                new_sad_list = sad_list
                new_surprise_list = surprise_list

            neutral_data_dict = {}
            neutral_data_dict['id'] = 'neutral'
            neutral_data_dict['data'] = new_neutral_list

            happy_data_dict = {}
            happy_data_dict['id'] = 'happy'
            happy_data_dict['data'] = new_happy_list

            sad_data_dict = {}
            sad_data_dict['id'] = 'sad'
            sad_data_dict['data'] = new_sad_list

            surprise_data_dict = {}
            surprise_data_dict['id'] = 'surprise'
            surprise_data_dict['data'] = new_surprise_list

            angry_data_dict = {}
            angry_data_dict['id'] = 'angry'
            angry_data_dict['data'] = new_angry_list

            data_list = []
            data_list.append(neutral_data_dict)
            data_list.append(happy_data_dict)
            data_list.append(sad_data_dict)
            data_list.append(surprise_data_dict)
            data_list.append(angry_data_dict)

            distribution_dict['graph_data'] = data_list

            recent_video_dict['distribution_data'] = distribution_dict
            recent_video_lists.append(recent_video_dict)

    # date_create_time을 기준으로 recent_video_lists를 정렬
    sorted_recent_video_lists = sorted(recent_video_lists, key=lambda x: x['date_create_time'], reverse=True)

    # 정렬된 리스트에서 앞에서 20개만 선택
    recent_20_sorted_recent_video_lists = sorted_recent_video_lists[:10]

    return recent_20_sorted_recent_video_lists

#최근 영상 데이터의 감정 목록 생성의 통계 데이터 생성
def make_recent_emotion_data(email_id):
    user_filter_query = {'user_email_id': email_id, 'user_activate' : 7} #userid로 user찾는 필터쿼리 user_filter_query
    user_document = collection_user.find_one(user_filter_query)
    user_index = user_document['user_index']

    recent_video_filter_query = {'user_index': user_index, 'watching_data_activate' : 7} #userid로 유저시청기록 찾는 쿼리
    recent_video_documents = collection_youtube_watching_data.find(recent_video_filter_query) #해당 유저의 모든 시청(감정분석기록) 검색

    recent_video_lists = [] #필요한 데이터들을 저장할 list

    for recent_video_document in recent_video_documents :
        youtube_index = recent_video_document['youtube_index']
        data_create_time = recent_video_document['data_create_time']
        neutral_per = recent_video_document['emotion_statistics_per']['neutral']
        if neutral_per == 'None' :
            neutral_per = float(0)
        happy_per = recent_video_document['emotion_statistics_per']['happy']
        if happy_per == 'None' :
            happy_per = float(0)
        surprise_per = recent_video_document['emotion_statistics_per']['surprise']
        if surprise_per == 'None' :
            surprise_per = float(0)
        sad_per = recent_video_document['emotion_statistics_per']['sad']
        if sad_per == 'None' :
            sad_per = float(0)
        angry_per = recent_video_document['emotion_statistics_per']['angry']
        if angry_per == 'None' :
            angry_per = float(0)
        flag = 1
        for recent_video_dict in recent_video_lists:
            this_youtube_index = recent_video_dict['youtube_index']
            if(youtube_index == this_youtube_index) :
                flag = 0
                break
        if(flag == 1) :
            recent_video_data = {
                'youtube_index' : youtube_index,
                'data_create_time' : data_create_time,
                'neutral_per' : neutral_per,
                'happy_per' : happy_per,
                'surprise_per' : surprise_per,
                'sad_per' : sad_per,
                'angry_per' : angry_per
            }
            recent_video_lists.append(recent_video_data)

    #최신순
    sorted_recent_video_lists = sorted(recent_video_lists, key=lambda x: x['data_create_time'], reverse=True)
    sorted_recent_video_lists = sorted_recent_video_lists[:10]
    
    recent_emotion_per_sum_dict = {
        'neutral_per_sum' : 0,
        'happy_per_sum' : 0,
        'surprise_per_sum' : 0,
        'sad_per_sum' : 0,
        'angry_per_sum' : 0
    }
    recent_emotion_per_num = 0
    for sorted_recent_video_dict in sorted_recent_video_lists:
        recent_emotion_per_sum_dict['neutral_per_sum'] += sorted_recent_video_dict['neutral_per']
        recent_emotion_per_sum_dict['happy_per_sum'] += sorted_recent_video_dict['happy_per']
        recent_emotion_per_sum_dict['surprise_per_sum'] += sorted_recent_video_dict['surprise_per']
        recent_emotion_per_sum_dict['sad_per_sum'] += sorted_recent_video_dict['sad_per']
        recent_emotion_per_sum_dict['angry_per_sum'] += sorted_recent_video_dict['angry_per']
        recent_emotion_per_num += 1

    recent_emotion_per_avg_dict= {}

    if recent_emotion_per_sum_dict['neutral_per_sum'] != 0 :
        neutral_per_avg = recent_emotion_per_sum_dict['neutral_per_sum']/recent_emotion_per_num
    else :
        neutral_per_avg = float(0)
    recent_emotion_per_avg_dict['neutral_per_avg'] = round(neutral_per_avg*100 , 2)

    if recent_emotion_per_sum_dict['happy_per_sum'] != 0 :
        happy_per_avg = recent_emotion_per_sum_dict['happy_per_sum']/recent_emotion_per_num
    else :
        happy_per_avg = float(0)
    recent_emotion_per_avg_dict['happy_per_avg'] = round(happy_per_avg*100 , 2)

    if recent_emotion_per_sum_dict['surprise_per_sum'] != 0 :
        surprise_per_avg = recent_emotion_per_sum_dict['surprise_per_sum']/recent_emotion_per_num
    else :
        surprise_per_avg = float(0)
    recent_emotion_per_avg_dict['surprise_per_avg'] = round(surprise_per_avg*100 , 2)

    if recent_emotion_per_sum_dict['sad_per_sum'] != 0 :
        sad_per_avg = recent_emotion_per_sum_dict['sad_per_sum']/recent_emotion_per_num
    else :
        sad_per_avg = float(0)
    recent_emotion_per_avg_dict['sad_per_avg'] = round(sad_per_avg*100 , 2)

    if recent_emotion_per_sum_dict['angry_per_sum'] != 0 :
        angry_per_avg = recent_emotion_per_sum_dict['angry_per_sum']/recent_emotion_per_num
    else :
        angry_per_avg = float(0)
    recent_emotion_per_avg_dict['angry_per_avg'] = round(angry_per_avg*100 , 2)

    return recent_emotion_per_avg_dict


########################################################################################################################
########################################################################################################################
########################################################################################################################
#유저의 모든 영상 시청기록에서 데이터 개수를 이용하여 유저가 감정을 느낀 시간 생성
def make_emotion_time_data(email_id):
    user_filter_query = {'user_email_id': email_id, 'user_activate' : 7} #userid로 user찾는 필터쿼리 user_filter_query
    user_document = collection_user.find_one(user_filter_query)
    user_index = user_document['user_index']

    recent_video_filter_query = {'user_index': user_index, 'watching_data_activate' : 7} #userid로 유저시청기록 찾는 쿼리
    recent_video_documents = collection_youtube_watching_data.find(recent_video_filter_query) #해당 유저의 모든 시청(감정분석기록) 검색

    emotion_num_dict = {
        'happy' : 0,
        'surprise' : 0,
        'sad' : 0,
        'angry' : 0,
        'neutral' : 0
    }

    for recent_video_document in recent_video_documents :
        youtube_index = recent_video_document['youtube_index']
        watching_data_index = recent_video_document['watching_data_index']

        youtube_filter_query = {'youtube_index' : youtube_index, 'youtube_activate' : 7}
        youtube_document = collection_youtube_video.find_one(youtube_filter_query)

        youtube_length_hour = youtube_document['youtube_length_hour']
        youtube_length_minute = youtube_document['youtube_length_minute']
        youtube_length_second = youtube_document['youtube_length_second']

        # 시작 시간
        start_time = timedelta(seconds=1)

        # 종료 시간
        end_time = timedelta(hours=youtube_length_hour, minutes=youtube_length_minute, seconds=youtube_length_second)

        # 시간 간격
        time_interval = timedelta(seconds=1)

        timeline_filter_query = {'watching_data_index' : watching_data_index}
        timeline_document = collection_youtube_watching_timeline.find_one(timeline_filter_query)
        #print(timeline_document)

        while start_time <= end_time:
            formatted_time = str(start_time)[0:10] #시간데이터 문자열 변환 00:00:00과같은 형식
            emotion_data = timeline_document[formatted_time]
            if emotion_data == 'happy' :
                emotion_num_dict['happy'] += 1
            elif emotion_data == 'neutral' :
                emotion_num_dict['neutral'] += 1
            elif emotion_data == 'surprise' :
                emotion_num_dict['surprise'] += 1
            elif emotion_data == 'sad' :
                emotion_num_dict['sad'] += 1
            elif emotion_data == 'angry' :
                emotion_num_dict['angry'] += 1

            start_time += time_interval

    return emotion_num_dict



#유저 이름 제공, /mypage/user-name
@mypage_blueprint.route('user-name', methods = ['GET', 'POST'])
def user_name():
    cur_access_token = request.headers.get('Authorization')

    verification_result = token_verification(cur_access_token)

    if verification_result == 'wrong token' :
        return jsonify({'message': 'This access token is Wrong'}), 408
    
    elif verification_result == 'expired token' :
        return jsonify({'message': 'This access token is expired'}), 408
    
    elif verification_result == 'non-existent user' :
        return jsonify({'message': 'User does not exist'}), 409
    
    elif verification_result == 'valid token' :
        decoded_token = decode_token(cur_access_token)
        email_id = decoded_token['id'] # 토큰에서 email_id 추출

        user_document = collection_user.find_one({'user_email_id': email_id, 'user_activate' : 7})
        user_name = user_document['user_name']

        return jsonify({'user_name' : user_name}), 200
    


# 최근 본 영상 목록, /mypage/recent-video로 라우팅
@mypage_blueprint.route('recent-video', methods = ['GET', 'POST'])
def recent_video():
    #잘못된 데이터베이스 수정
    watching_documents = collection_youtube_watching_data.find()
    
    for watching_document in watching_documents :
        this_id = watching_document['_id']
        this_watching_index = watching_document['watching_data_index']
        for check_document in watching_documents :
            check_watching_index = check_document['watching_data_index']
            check_id = check_document['_id']
            if check_watching_index == this_watching_index :
                if this_id != check_id :
                    modify_filter_query = {'_id' : check_id}
                    watching_data_document = collection_youtube_watching_data.find().sort('watching_data_index', -1).limit(1) # watching_data_index를 내림차순으로 정렬
                    watching_data_max_index = int(watching_data_document[0]['watching_data_index']) # user_seq 값만 저장
                    new_index = watching_data_max_index + 1
                    modify_update_query = {'$set' : {'watching_data_index' : new_index}}
                    collection_youtube_watching_data.update_one(modify_filter_query, modify_update_query)
                    collection_youtube_watching_timeline.update_one(modify_filter_query, modify_update_query)
                    collection_youtube_watching_timeline_data.update_one(modify_filter_query, modify_update_query)

    #잘못된 데이터베이스 제거
    watching_data_filter_query = {'most_emotion' : 'None', 'watching_achivement_per' : 'None'}
    trash_documents = collection_youtube_watching_data.find(watching_data_filter_query)

    for trash_document in trash_documents :
        watching_trash_data_index = trash_document['watching_data_index']
        print(watching_trash_data_index)
        watching_filter_query = {'watching_data_index' : watching_trash_data_index}
        result1 = collection_youtube_watching_data.delete_one(watching_filter_query)
        result2 = collection_youtube_watching_timeline.delete_one(watching_filter_query)
        result3 = collection_youtube_watching_timeline_data.delete_one(watching_filter_query)
    
    cur_access_token = request.headers.get('Authorization')

    verification_result = token_verification(cur_access_token)

    if verification_result == 'wrong token' :
        return jsonify({'message': 'This access token is Wrong'}), 408
    
    elif verification_result == 'expired token' :
        return jsonify({'message': 'This access token is expired'}), 408
    
    elif verification_result == 'non-existent user' :
        return jsonify({'message': 'User does not exist'}), 409
    
    elif verification_result == 'valid token' :
        decoded_token = decode_token(cur_access_token)
        email_id = decoded_token['id'] # 토큰에서 email_id 추출

        recent_20_video_list = make_recent_list(email_id)

        return jsonify(recent_20_video_list), 200


# 해당유저의 최근 시청기록에서의 도넛차트를 위한 리스트
@mypage_blueprint.route('donut-data', methods = ['GET', 'POST'])
def donut_data():
    cur_access_token = request.headers.get('Authorization')

    verification_result = token_verification(cur_access_token)

    if verification_result == 'wrong token' :
        return jsonify({'message': 'This access token is Wrong'}), 408
    
    elif verification_result == 'expired token' :
        return jsonify({'message': 'This access token is expired'}), 408
    
    elif verification_result == 'non-existent user' :
        return jsonify({'message': 'User does not exist'}), 409
    
    elif verification_result == 'valid token' :
        decoded_token = decode_token(cur_access_token)
        email_id = decoded_token['id'] # 토큰에서 email_id 추출

        recent_emotion_data = make_recent_emotion_data(email_id)

        return recent_emotion_data, 200


# 해당 유저의 감정 누적기록 가져오자
@mypage_blueprint.route('all-emotion-num', methods = ['GET', 'POST'])
def all_emotion_num():
    cur_access_token = request.headers.get('Authorization')

    verification_result = token_verification(cur_access_token)

    if verification_result == 'wrong token' :
        return jsonify({'message': 'This access token is Wrong'}), 408
    
    elif verification_result == 'expired token' :
        return jsonify({'message': 'This access token is expired'}), 408
    
    elif verification_result == 'non-existent user' :
        return jsonify({'message': 'User does not exist'}), 409
    
    elif verification_result == 'valid token' :
        decoded_token = decode_token(cur_access_token)
        email_id = decoded_token['id'] # 토큰에서 email_id 추출

        all_emotion_num_dict = make_emotion_time_data(email_id)

        return(all_emotion_num_dict), 200


# 비밀번호 변경, /mypage/change-pw로 라우팅
@mypage_blueprint.route('change-pw', methods = ['GET', 'POST'])
def change_pw():
    user_data = request.get_json()
    cur_access_token = request.headers.get('Authorization')
    cur_password = user_data.get('cur_password', None)
    new_password = user_data.get('new_password', None)

    if not cur_password or not new_password: # 현재비밀번호와 새로운비밀번호를 입력하지 않았을 때 400
        return jsonify({'message': 'cur_password and new_password are required.'}), 400

    verification_result = token_verification(cur_access_token)

    if verification_result == 'wrong token' :
        return jsonify({'message': 'This access token is Wrong'}), 408
    
    elif verification_result == 'expired token' :
        return jsonify({'message': 'This access token is expired'}), 408
    
    elif verification_result == 'non-existent user' :
        return jsonify({'message': 'User does not exist'}), 409
    
    elif verification_result == 'valid token' :
        decoded_token = decode_token(cur_access_token)
        email_id = decoded_token['id'] # 토큰에서 email_id 추출

        user_filter_query = {'user_id': email_id, 'user_activate' : 7} #userid로 user찾는 필터쿼리 user_filter_query
        user_document = collection_user.find_one(user_filter_query)
        user_password = user_document['user_pw']

        # 현재 패스워드 검사
        if not bcrypt.checkpw(cur_password.encode('utf-8'), user_password.encode('utf-8')):
            return jsonify({'message': 'cur_password does not match.'}), 401
        
        # 비밀번호 형식 검사 (8자 이상, 64자이하, 숫자 포함)
        if not re.match(r'^(?=.*\d)(?=.*[a-zA-Z]).{8,64}$', new_password):
            return jsonify({'message': 'Password must be at least 8 characters and must contain numbers.'}), 400
        
        pw_encrypted = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()) #새로운 비밀번호 암호화
        decoded_pw = pw_encrypted.decode('utf-8') #해시 문자 변환

        pw_update_query = {'$set': {'user_pw': decoded_pw}} #업데이트 쿼리 user_update_query

        result = collection_user.update_one(user_filter_query, pw_update_query)

        return jsonify({'message': 'Successful password change'}), 200
    

# 이름 변경, /mypage/change-name로 라우팅
@mypage_blueprint.route('change-name', methods = ['GET', 'POST'])
def change_name():
    cur_access_token = request.headers.get('Authorization')
    user_data = request.get_json()
    new_name = user_data.get('new_name', None)

    if not new_name : # 새로운 이름을 입력하지 않았을 때 400
        return jsonify({'message': 'new_name are required.'}), 400

    verification_result = token_verification(cur_access_token)

    if verification_result == 'wrong token' :
        return jsonify({'message': 'This access token is Wrong'}), 408
    
    elif verification_result == 'expired token' :
        return jsonify({'message': 'This access token is expired'}), 408
    
    elif verification_result == 'non-existent user' :
        return jsonify({'message': 'User does not exist'}), 409
    
    elif verification_result == 'valid token' :
        # 닉네임 형식 검사
        #print(new_name)
        if not re.match(r'^.{2,10}$', new_name):
            return jsonify({'message': 'Nickname must be between 2 and 10 characters.'}), 400
        decoded_token = decode_token(cur_access_token)
        email_id = decoded_token['id'] # 토큰에서 email_id 추출

        user_filter_query = {'user_email_id': email_id}
        name_update_query = {'$set': {'user_name': new_name}}
        result = collection_user.update_one(user_filter_query, name_update_query)

        return jsonify({'message': 'Successful name change'}), 200


# 프로필 사진 변경, /mypage/change-profilephoto로 라우팅
@mypage_blueprint.route('change-profilephoto', methods = ['GET', 'POST'])
def change_profilephoto():
    user_data = request.get_json()
    cur_access_token = request.headers.get('Authorization')
    new_profile = user_data.get('new_profile', None)
    
    verification_result = token_verification(cur_access_token)

    if verification_result == 'wrong token' :
        return jsonify({'message': 'This access token is Wrong'}), 408
    
    elif verification_result == 'expired token' :
        return jsonify({'message': 'This access token is expired'}), 408
    
    elif verification_result == 'non-existent user' :
        return jsonify({'message': 'User does not exist'}), 409
    
    elif verification_result == 'valid token' :
        decoded_token = decode_token(cur_access_token)
        email_id = decoded_token['id'] # 토큰에서 email_id 추출

        user_filter_query = {'user_email_id': email_id}
        profile_update_query = {'$set': {'user_profile': new_profile}}
        result = collection_user.update_one(user_filter_query, profile_update_query)

        return jsonify({'message': 'Successful profile change'}), 200


# 선호 장르 변경, /mypage/change-favorite-genre로 라우팅
@mypage_blueprint.route('change-favorite-genre', methods = ['GET', 'POST'])
def change_favorite_genre():
    user_data = request.get_json()
    cur_access_token = request.headers.get('Authorization')
    user_favorite_genre_1 = user_data.get('user_favorite_genre_1', None)
    user_favorite_genre_2 = user_data.get('user_favorite_genre_2', None)
    user_favorite_genre_3 = user_data.get('user_favorite_genre_3', None)

    verification_result = token_verification(cur_access_token)

    if verification_result == 'wrong token' :
        return jsonify({'message': 'This access token is Wrong'}), 408
    
    elif verification_result == 'expired token' :
        return jsonify({'message': 'This access token is expired'}), 408
    
    elif verification_result == 'non-existent user' :
        return jsonify({'message': 'User does not exist'}), 409
    
    elif verification_result == 'valid token' :
        decoded_token = decode_token(cur_access_token)
        email_id = decoded_token['id'] # 토큰에서 email_id 추출

        user_filter_query = {'user_email_id': email_id}
        genre_update_query = {'$set': {'user_favorite_genre_1': user_favorite_genre_1, 
            'user_favorite_genre_2':user_favorite_genre_2, 'user_favorite_genre_3':user_favorite_genre_3}}
        result = collection_user.update_one(user_filter_query, genre_update_query)

        return jsonify({'message': 'Successful favorite genre change'}), 200
    