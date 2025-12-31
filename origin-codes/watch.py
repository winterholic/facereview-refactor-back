# -*- coding: utf-8 -*-
from flask import Flask, render_template, Response, jsonify, Blueprint, request
from flask_socketio import SocketIO, emit
from datetime import datetime, timedelta
import io
import random
from PIL import Image
import numpy as np
import cvlib as cv
import cv2
import base64
from tensorflow import keras
from pymongo import MongoClient
from gate import token_verification
from jwtfunction import decode_token, create_access_token, create_refresh_token



#blueprint 연결
watch_blueprint = Blueprint("watch", __name__, url_prefix='/watch')


# emotion list
emotion = ["happy", "surprise", "angry", "sad", "neutral"] 


# load model
model = keras.models.load_model('model.h5')


# MongoDB 연결 설정
client = MongoClient('mongodb://localhost:27017/')
db = client.FaceReview_Database
collection_user = db.user
collection_youtube_video = db.youtube_video
collection_video_distribution = db.video_distribution
collection_youtube_watching_data = db.youtube_watching_data
collection_youtube_inquiry = db.youtube_inquiry
collection_youtube_watching_timeline = db.youtube_watching_timeline
collection_timeline_emotion_num = db.timeline_emotion_num
collection_timeline_emotion_per = db.timeline_emotion_per
collection_timeline_emotion_most = db.timeline_emotion_most
collection_comment = db.comment
collection_like = db.like



#유저의 엑세스토큰에 대해 검증(소켓에서는 만료여부는 검증하지 않기 때문), /watch/detail-page-verify-token로 라우팅
@watch_blueprint.route('detail-page-verify-token', methods = ['GET', 'POST'])
def verify_token_detail_page():
    user_data = request.get_json()
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

        user_data = {
            'user_name' : user_name # 근데 딱히 유저 정보 필요없어보여서 필요없으면 메세지만 전송하도록 수정
        }

        return jsonify({'message': 'This access token is valid'}, user_data), 200 # 클라이언트가 필요로 하는 유저의 정보 전송

######################################################################################################################
######################################################################################################################
######################################################################################################################
######################################################################################################################

#유저가 시청하는 메인 영상, /watch/main-youtube로 라우팅
@watch_blueprint.route('main-youtube', methods = ['GET', 'POST'])
def gain_main_youtube_url():
    data = request.get_json()
    youtube_url = data.get('youtube_url', None)
    #print(data)
    
    url_filter_query = {'youtube_url': youtube_url, 'youtube_activate' : 7}
    youtube_document = collection_youtube_video.find_one(url_filter_query) #youtube_url로 youtube_video 테이블 검색
    youtube_index = youtube_document['youtube_index']

    like_num_filter_query = {'youtube_index' : youtube_index, 'like_activate' : 7}
    like_num = collection_like.count_documents(like_num_filter_query)

    youtube_index = youtube_document['youtube_index']
    youtube_title = youtube_document['youtube_title']
    youtube_channel = youtube_document['youtube_channel']
    youtube_comment_num = youtube_document['youtube_comment_num']
    youtube_hits = youtube_document['youtube_hits']
    youtube_like = like_num

    main_youtube_url = { #main_youtube_url 딕셔너리에 youtube_index, youtube_url, youtube_title, youtube_channel, youtube_comment_num 항목 포함
        'youtube_index' : youtube_index,
        'youtube_url': youtube_url,
        'youtube_title' : youtube_title,
        'youtube_channel' : youtube_channel,
        'youtube_comment_num' : youtube_comment_num,
        'youtube_hits' : youtube_hits,
        'youtube_like' : youtube_like
    }

    return jsonify(main_youtube_url), 200

######################################################################################################################

#메인 영상 감정분석 데이터, /watch/main-distribution-data로 라우팅
@watch_blueprint.route('main-distribution-data', methods = ['GET', 'POST'])
def gain_main_distribution_data():
    data = request.get_json()
    youtube_url = data.get('youtube_url', None)

    url_filter_query = {'youtube_url': youtube_url, 'youtube_activate' : 7}
    youtube_document = collection_youtube_video.find_one(url_filter_query) #youtube_url로 youtube_video 테이블 검색
    youtube_index = youtube_document['youtube_index']

    timeline_emotion_filter_query = {'youtube_index' : youtube_index, 'timeline_emotion_most_activate' : 7}
    timeline_emotion_document = collection_timeline_emotion_most.find_one(timeline_emotion_filter_query)

    timeline_per_filter_query = {'youtube_index' : youtube_index, 'timeline_emotion_per_activate' : 7}
    timeline_per_document = collection_timeline_emotion_per.find_one(timeline_per_filter_query)
    #print(timeline_per_document)

    

    youtube_length_hour = youtube_document['youtube_length_hour']
    youtube_length_minute = youtube_document['youtube_length_minute']
    youtube_length_second = youtube_document['youtube_length_second']

    if not timeline_emotion_document : 
        distribution_dict = {}
        start_time = timedelta(seconds=1)
        end_time = timedelta(hours=youtube_length_hour, minutes=youtube_length_minute, seconds=youtube_length_second)
        time_interval = timedelta(seconds=1)
        happy_list = []
        neutral_list = []
        angry_list = []
        sad_list = []
        surprise_list = []

        while start_time <= end_time:
            formatted_time = str(start_time)[0:10] #시간데이터 문자열 변환 00:00:00과같은 형식
            happy_per = float(0)
            neutral_per = float(0)
            angry_per = float(0)
            sad_per = float(0)
            surprise_per = float(0)

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

            start_time += time_interval

        distribution_dict['happy'] = happy_list
        distribution_dict['neutral'] = neutral_list
        distribution_dict['angry'] = angry_list
        distribution_dict['sad'] = sad_list
        distribution_dict['surprise'] = happy_list

        return jsonify(distribution_dict), 200

    distribution_dict = {}

    # 시작 시간
    start_time = timedelta(seconds=1)

    # 종료 시간
    end_time = timedelta(hours=youtube_length_hour, minutes=youtube_length_minute, seconds=youtube_length_second)

    # 시간 간격
    time_interval = timedelta(seconds=1)

    happy_list = []
    neutral_list = []
    angry_list = []
    sad_list = []
    surprise_list = []

    data_num = 0

    while start_time <= end_time:
        formatted_time = str(start_time)[0:10] #시간데이터 문자열 변환 00:00:00과같은 형식
        
        #데이터 불러오기
        happy_per = round(timeline_per_document[formatted_time]['happy']*100 , 1)
        neutral_per = round(timeline_per_document[formatted_time]['neutral']*100, 1)
        angry_per = round(timeline_per_document[formatted_time]['angry']*100, 1)
        sad_per = round(timeline_per_document[formatted_time]['sad']*100, 1)
        surprise_per = round(timeline_per_document[formatted_time]['surprise']*100, 1)

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

    tmp_num = data_num / 100
    Parameter = round(tmp_num, 0)
    #print(Parameter)

    #print(happy_list)
    print(data_num)

    if data_num > 100 :
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

    distribution_dict['happy'] = new_happy_list
    distribution_dict['neutral'] = new_neutral_list
    distribution_dict['angry'] = new_angry_list
    distribution_dict['sad'] = new_sad_list
    distribution_dict['surprise'] = new_happy_list

    #print(distribution_dict)

    return jsonify(distribution_dict), 200

######################################################################################################################

#youtube_url로 emotion과 category를 반환해주는 메소드
def find_emotion_and_category(youtube_url):
    url_filter_query = {'youtube_url': youtube_url, 'youtube_activate' : 7}
    youtube_document = collection_youtube_video.find_one(url_filter_query) #youtube_url로 youtube_video 테이블 검색

    youtube_index = youtube_document['youtube_index']
    youtube_category = youtube_document['youtube_category']

    emotion_filter_query = {'youtube_index': youtube_index, 'distribution_activate' : 7}
    distribution_document = collection_video_distribution.find_one(emotion_filter_query)

    youtube_emotion = distribution_document['most_emotion']

    this_dict = {
        'youtube_category' : youtube_category,
        'youtube_emotion' : youtube_emotion,
        'youtube_index' : youtube_index
    }
    return this_dict

######################################################################################################################

#emotion_score측정
def choise_emotion_score(this_emotion, neutral_statistics_score, happy_statistics_score, surprise_statistics_score, sad_statistics_score, angry_statistics_score) :
    if this_emotion == 'neutral' :
        emotion_score = neutral_statistics_score
    elif this_emotion == 'happy' :
        emotion_score = happy_statistics_score
    elif this_emotion == 'surprise' :
        emotion_score = surprise_statistics_score
    elif this_emotion == 'sad' :
        emotion_score = sad_statistics_score
    elif this_emotion == 'angry' :
        emotion_score = angry_statistics_score
    elif this_emotion == 'None' :
        emotion_score = float(0)
    return emotion_score

######################################################################################################################

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

######################################################################################################################

#해당영상과 같은 장르이거나 같은 감정분포를 가지면서. 
def make_recommend_list(original_index, this_emotion, this_category):
    # 동일한 카테고리 기반 category_emotion_lists 추가
    category_filter_query = {'youtube_category': this_category, 'youtube_activate' : 7} # 해당 카테고리인 유튜브 영상 테이블 검색
    category_documents = collection_youtube_video.find(category_filter_query)

    category_emotion_lists = [] # 필요한 데이터를 저장할 리스트

    for category_document in category_documents : # 카테고리 도큐먼트들 for문
        youtube_index = category_document['youtube_index'] # 해당영상의 youtube index를 이용한 distribution검색
        youtube_url = category_document['youtube_url']
        distribution_filter_query = {'youtube_index': youtube_index, 'distribution_activate' : 7}
        distribution_document = collection_video_distribution.find_one(distribution_filter_query)
        if youtube_index != original_index : # 현재 보고 있는 영상은 제외한다.
            youtube_title = category_document['youtube_title']
            youtube_emotion = distribution_document['most_emotion']

            neutral_statistics_score = distribution_document['emotion_statistics_score']['neutral']
            happy_statistics_score = distribution_document['emotion_statistics_score']['happy']
            surprise_statistics_score = distribution_document['emotion_statistics_score']['surprise']
            sad_statistics_score = distribution_document['emotion_statistics_score']['sad']
            angry_statistics_score = distribution_document['emotion_statistics_score']['angry']

            emotion_score = choise_emotion_score(youtube_emotion, neutral_statistics_score, happy_statistics_score, surprise_statistics_score, sad_statistics_score, angry_statistics_score)

            neutral_statistics_per = distribution_document['emotion_statistics_avg']['neutral']
            happy_statistics_per = distribution_document['emotion_statistics_avg']['happy']
            surprise_statistics_per = distribution_document['emotion_statistics_avg']['surprise']
            sad_statistics_per = distribution_document['emotion_statistics_avg']['sad']
            angry_statistics_per = distribution_document['emotion_statistics_avg']['angry']
            emotion_per = choise_emotion_per(youtube_emotion, neutral_statistics_per, happy_statistics_per, surprise_statistics_per, sad_statistics_per, angry_statistics_per)

            category_emotion_dict = {
                'youtube_url' : youtube_url, # url, 나중에 전송할 데이터
                'youtube_title' : youtube_title, # title, 나중에 전송할 데이터
                'most_emotion' : youtube_emotion, # emotion, 나중에 전송할 데이터
                'emotion_score' : emotion_score, # emotion_score, 정렬을 위한 데이터
                'emotion_per' : emotion_per, # emotion_per, 나중에 전송할 데이터
                'youtube_category' : this_category
            }

            category_emotion_lists.append(category_emotion_dict)

    # 감정 기반으로 category_emotion_lists 추가
    if this_emotion != 'None' :
        distribution_filter_query = {'most_emotion': this_emotion, 'distribution_activate' : 7}
        distribution_documents = collection_video_distribution.find(distribution_filter_query)
        for distribution_document in distribution_documents :
            youtube_index = distribution_document['youtube_index']

            if youtube_index != original_index : # 현재 보고 있는 영상은 제외한다.
                index_filter_query = {'youtube_index': youtube_index, 'youtube_activate' : 7} # 해당 카테고리인 유튜브 영상 테이블 검색
                index_document = collection_youtube_video.find_one(index_filter_query)
                youtube_url = index_document['youtube_url']
                youtube_title = index_document['youtube_title']
                youtube_category = index_document['youtube_category']
            
                neutral_statistics_score = distribution_document['emotion_statistics_score']['neutral']
                happy_statistics_score = distribution_document['emotion_statistics_score']['happy']
                surprise_statistics_score = distribution_document['emotion_statistics_score']['surprise']
                sad_statistics_score = distribution_document['emotion_statistics_score']['sad']
                angry_statistics_score = distribution_document['emotion_statistics_score']['angry']

                emotion_score = choise_emotion_score(this_emotion, neutral_statistics_score, happy_statistics_score, surprise_statistics_score, sad_statistics_score, angry_statistics_score)

                neutral_statistics_per = distribution_document['emotion_statistics_avg']['neutral']
                happy_statistics_per = distribution_document['emotion_statistics_avg']['happy']
                surprise_statistics_per = distribution_document['emotion_statistics_avg']['surprise']
                sad_statistics_per = distribution_document['emotion_statistics_avg']['sad']
                angry_statistics_per = distribution_document['emotion_statistics_avg']['angry']
                emotion_per = choise_emotion_per(this_emotion, neutral_statistics_per, happy_statistics_per, surprise_statistics_per, sad_statistics_per, angry_statistics_per)

                category_emotion_dict = {
                    'youtube_url' : youtube_url, # url, 나중에 전송할 데이터
                    'youtube_title' : youtube_title, # title, 나중에 전송할 데이터
                    'most_emotion' : this_emotion, # emotion, 나중에 전송할 데이터
                    'emotion_score' : emotion_score, # emotion_score, 정렬을 위한 데이터
                    'emotion_per' : emotion_per, # emotion_per, 나중에 전송할 데이터
                    'youtube_category' : youtube_category
                }
                flag = 1
                for category_emotion_list in category_emotion_lists :
                    list_youtube_url = category_emotion_list['youtube_url']
                    this_url = youtube_url
                    if(list_youtube_url == this_url) :
                        flag = 0
                        break
                if flag == 1 :
                    category_emotion_lists.append(category_emotion_dict)
    
    sorted_category_emotion_lists = sorted(category_emotion_lists , key=lambda x: x['emotion_score'], reverse=True) #emotion_score순서로 데이터 정렬

    new_data_list = []

    for sorted_category_emotion_list in sorted_category_emotion_lists :
        if this_emotion == sorted_category_emotion_list['most_emotion'] :
            if this_category == sorted_category_emotion_list['youtube_category'] :
                temp_dict = sorted_category_emotion_list
                new_data_list.append(temp_dict)

    for sorted_category_emotion_list in sorted_category_emotion_lists :
        flag = 1
        check_url = sorted_category_emotion_list['youtube_url']
        for new_data_dict in new_data_list :
            if(check_url == new_data_dict['youtube_url']) :
                flag = 0
                break
        if flag == 1 :
            new_data_list.append(sorted_category_emotion_list)
    
    emotion_category_lists = []
    for temp_list in new_data_list :
        youtube_url = temp_list['youtube_url']
        youtube_title = temp_list['youtube_title']
        most_emotion = temp_list['most_emotion']
        emotion_per = round(temp_list['emotion_per']*100, 2)
        temp_dict = {
            'youtube_url' : youtube_url,
            'youtube_title' : youtube_title,
            'most_emotion' : most_emotion,
            'emotion_per' : emotion_per
        }
        emotion_category_lists.append(temp_dict)

    emotion_category_lists = emotion_category_lists[:10]

    # 같은 emotion, category 중 emotion_score가 높은 10개 리턴
    return emotion_category_lists

######################################################################################################################

#옆에 뜰 추천 영상 목록 5개정도면 적당하지만 혹시몰라서 10개까지, /watch/sub-youtube로 라우팅
@watch_blueprint.route('/sub-youtube', methods = ['GET', 'POST'])
def gain_sub_youtube_url():
    data = request.get_json()
    youtube_url = data.get('youtube_url', None)
    emotion_category_dict = find_emotion_and_category(youtube_url)
    
    original_index = emotion_category_dict['youtube_index']
    this_emotion  = emotion_category_dict['youtube_emotion']
    this_category = emotion_category_dict['youtube_category']
    
    #같은 emotion, 같은 category, emotion_score가 높은 영상 10개 리스트 가져오기
    same_emotion_category_rec_list = make_recommend_list(original_index, this_emotion, this_category)
    
    return jsonify(same_emotion_category_rec_list), 200

######################################################################################################################

#조회수 컨트롤 같은 유저는 1의 조회수만 가질 수 있도록 update, (아 좋아요기능도 짜야하네...) /watch/update-hits로 라우팅
@watch_blueprint.route('/update-hits', methods = ['GET', 'POST'])
def update_hits():
    data = request.get_json()
    youtube_url = data.get('youtube_url', None)
    youtube_filter_query = {'youtube_url' : youtube_url, 'youtube_activate' : 7}
    youtube_document = collection_youtube_video.find_one(youtube_filter_query)
    youtube_index = youtube_document['youtube_index']
    user_categorization = data.get('user_categorization', None)
    cur_access_token = request.headers.get('Authorization') # 임시 토큰이든, 유저의 토큰이든 똑같이 cur_access_token에 담아서 보냄

    if user_categorization == 'user' : # 유저인 경우
        # 먼저 토큰을 검증한다
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

            #inquiry 검색
            inquiry_filter_query = {'youtube_index' : youtube_index, 'user_id' : email_id, 'inquiry_activate' : 7}
            inquiry_document = collection_youtube_inquiry.find_one(inquiry_filter_query)
            if inquiry_document :
                return jsonify({'message' : 'The user inquiry history already exists.'}), 200
            else :
                # 콜렉션 내의 도큐먼트 수 확인
                document_count = collection_youtube_inquiry.count_documents({})
                index_max_value = document_count + 1
                collection_youtube_inquiry.insert_one({
                    'inquiry_index' : index_max_value,
                    'youtube_index' : youtube_index,
                    'user_id' : email_id,
                    'user_token' : 'None',
                    'inquiry_activate' : 7
                })
                update_hits_filter_query = {'youtube_index' : youtube_index}
                update_hits_update_query = {'$inc' : {'youtube_hits' : +1}}
                result = collection_youtube_video.update_one(update_hits_filter_query, update_hits_update_query)

                return jsonify({'message' : 'view count has been successfully updated.'}), 200
            
    elif user_categorization == 'non-user' : #유저가 아닌 경우
        #inquiry 검색
        inquiry_filter_query = {'youtube_index' : youtube_index, 'user_token' : cur_access_token, 'inquiry_activate' : 7}
        inquiry_document = collection_youtube_inquiry.find_one(inquiry_filter_query)
        if inquiry_document :
            return jsonify({'message' : 'The user inquiry history already exists.'}), 200
        else :
            # 콜렉션 내의 도큐먼트 수 확인
            document_count = collection_youtube_inquiry.count_documents({})
            index_max_value = document_count + 1
            collection_youtube_inquiry.insert_one({
                'inquiry_index' : index_max_value,
                'youtube_index' : youtube_index,
                'user_id' : 'None',
                'user_token' : cur_access_token,
                'inquiry_activate' : 7
            })
            update_hits_filter_query = {'youtube_index' : youtube_index}
            update_hits_update_query = {'$inc' : {'youtube_hits' : +1}}
            result = collection_youtube_video.update_one(update_hits_filter_query, update_hits_update_query)

            return jsonify({'message' : 'view count has been successfully updated.'}), 200

######################################################################################################################


#댓글 달기 기능, /watch/comment-list로 라우팅
@watch_blueprint.route('add-comment', methods = ['GET', 'POST'])
def add_comment():
    data = request.get_json()
    contents = data.get('comment_contents', None)
    youtube_url = data.get('youtube_url', None)
    youtube_filter_query = {'youtube_url' : youtube_url, 'youtube_activate' : 7}
    youtube_document = collection_youtube_video.find_one(youtube_filter_query)
    youtube_index = youtube_document['youtube_index']
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

        user_filter_query = {'user_email_id': email_id, 'user_activate' : 7} #userid로 user찾는 필터쿼리 user_filter_query
        user_document = collection_user.find_one(user_filter_query)
        user_index = user_document['user_index']

        document_count = collection_comment.count_documents({})
        index_max_value = document_count + 1
        comment_index = index_max_value
        comment_date = datetime.utcnow()
        comment_contents = contents
        comment_activate = 7

        collection_comment.insert_one({
            'comment_index' : comment_index,
            'youtube_index' : youtube_index,
            'user_index' : user_index,
            'comment_date' : comment_date,
            'comment_contents' : comment_contents,
            'modify_check' : 0,
            'comment_activate' : comment_activate
        })

        #댓글 개수 재 계산
        youtube_filter_query = {'youtube_index' : youtube_index, 'youtube_activate' : 7}
        youtube_update_query = {'$inc' : {'youtube_comment_num' : +1}}
        result = collection_youtube_video.update_one(youtube_filter_query, youtube_update_query)

        return jsonify({'message' : 'Comments have been added'}), 200

######################################################################################################################

#댓글 목록 불러오기, /watch/comment-list로 라우팅
@watch_blueprint.route('comment-list', methods = ['GET', 'POST'])
def comment_list():
    data = request.get_json()
    youtube_url = data.get('youtube_url', None)
    youtube_filter_query = {'youtube_url' : youtube_url, 'youtube_activate' : 7}
    youtube_document = collection_youtube_video.find_one(youtube_filter_query)
    youtube_index = youtube_document['youtube_index']

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

        user_filter_query = {'user_email_id': email_id, 'user_activate' : 7} #userid로 user찾는 필터쿼리 user_filter_query
        user_document = collection_user.find_one(user_filter_query)
        user_index = user_document['user_index']
        
        comment_filter_query = {'youtube_index' : youtube_index, 'comment_activate' : 7}
        comment_documents = collection_comment.find(comment_filter_query)

        comment_list = []
        for comment_document in comment_documents :
            comment_index = comment_document['comment_index']
            comment_user_index = comment_document['user_index']
            comment_date = comment_document['comment_date']
            comment_contents = comment_document['comment_contents']
            modify_check = comment_document['modify_check']

            user_filter_query = {'user_index' : comment_user_index, 'user_activate' : 7}
            comment_user_document = collection_user.find_one(user_filter_query)
            user_name = comment_user_document['user_name']
            user_profile = comment_user_document['user_profile']
    
            str_comment_date = comment_date.isoformat()
            
            if user_index == comment_user_index :
                comment_dict = {
                    'comment_index' : comment_index,
                    'user_name' : user_name,
                    'user_profile' : user_profile,
                    'comment_date' : str_comment_date,
                    'modify_check' : modify_check,
                    'comment_contents' : comment_contents,
                    'identify' : 1 # 내가 단 댓글일 때
                }
            else :
                comment_dict = {
                    'comment_index' : comment_index,
                    'user_name' : user_name,
                    'user_profile' : user_profile,
                    'comment_date' : str_comment_date,
                    'modify_check' : modify_check,
                    'comment_contents' : comment_contents,
                    'identify' : 0 # 내가 단 댓글 아닐 때
                }
            comment_list.append(comment_dict)
        comment_list.sort(key=lambda x: x['comment_date'], reverse=True)
        return jsonify(comment_list), 200

######################################################################################################################

#댓글 수정하기, /watch/modify-comment
@watch_blueprint.route('modify-comment', methods = ['GET', 'POST'])
def modify_comment():
    data = request.get_json()
    comment_index = data.get('comment_index', None)
    new_contents = data.get('new_comment_contents', None)

    comment_date = datetime.utcnow()
    comment_contents = new_contents
    modify_check = 1
    
    comment_filter_query = {'comment_index' : comment_index, 'comment_activate' : 7}
    comment_update_query = {'$set' : {'comment_date' : comment_date, 'comment_contents' : comment_contents, 'modify_check' : modify_check}}
    result = collection_comment.update_one(comment_filter_query, comment_update_query)

    return jsonify({'message' : 'Comments have been modified'}), 200

######################################################################################################################

#댓글 삭제하기, /watch/delete-comment
@watch_blueprint.route('delete-comment', methods = ['GET', 'POST'])
def delete_comment():
    data = request.get_json()
    comment_index = data.get('comment_index', None)

    comment_filter_query = {'comment_index' : comment_index, 'comment_activate' : 7}
    comment_document = collection_comment.find_one(comment_filter_query)
    youtube_index = comment_document['youtube_index']

    #댓글 비활성화
    comment_update_query = {'$set' : {'comment_activate' : 0}}
    result = collection_comment.update_one(comment_filter_query, comment_update_query)

    #댓글 개수 재 계산
    youtube_filter_query = {'youtube_index' : youtube_index, 'youtube_activate' : 7}
    youtube_update_query = {'$inc' : {'youtube_comment_num' : -1}}
    result = collection_youtube_video.update_one(youtube_filter_query, youtube_update_query)

    return jsonify({'message' : 'Comments have been deleted'}), 200

#댓글 달기 기능, /watch/add-like로 라우팅
@watch_blueprint.route('add-like', methods = ['GET', 'POST'])
def add_like():
    data = request.get_json()
    youtube_url = data.get('youtube_url', None)
    youtube_filter_query = {'youtube_url' : youtube_url, 'youtube_activate' : 7}
    youtube_document = collection_youtube_video.find_one(youtube_filter_query)
    youtube_index = youtube_document['youtube_index']
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

        user_filter_query = {'user_email_id': email_id, 'user_activate' : 7} #userid로 user찾는 필터쿼리 user_filter_query
        user_document = collection_user.find_one(user_filter_query)
        user_index = user_document['user_index']

        like_filter_query = {'user_index' : user_index, 'youtube_index' : youtube_index}
        like_document = collection_like.find_one(like_filter_query)

        if not like_document :
            document_count = collection_like.count_documents({})
            index_max_value = document_count + 1
            like_index = index_max_value
            like_date = datetime.utcnow()
            like_activate = 7

            collection_like.insert_one({
                'like_index' : like_index,
                'youtube_index' : youtube_index,
                'user_index' : user_index,
                'like_date' : like_date,
                'like_activate' : like_activate
            })

            #좋아요 수 재 계산
            youtube_filter_query = {'youtube_index' : youtube_index, 'youtube_activate' : 7}
            youtube_update_query = {'$inc' : {'youtube_like' : +1}}
            result = collection_youtube_video.update_one(youtube_filter_query, youtube_update_query)

            return jsonify({'message' : 'Comments have been added'}), 200
        
        else :
            like_index = like_document['like_index']
            like_filter_query = {'like_index' : like_index}
            like_update_query = {'$set' : {'like_activate' : 7}}
            result = collection_like.update_one(like_filter_query, like_update_query)

            #좋아요 수 재 계산
            youtube_filter_query = {'youtube_index' : youtube_index, 'youtube_activate' : 7}
            youtube_update_query = {'$inc' : {'youtube_like' : +1}}
            result = collection_youtube_video.update_one(youtube_filter_query, youtube_update_query)

            return jsonify({'message' : 'like have been added'}), 200


#댓글 달기 기능, /watch/cancel-like로 라우팅
@watch_blueprint.route('cancel-like', methods = ['GET', 'POST'])
def cancel_like():
    data = request.get_json()
    youtube_url = data.get('youtube_url', None)
    youtube_filter_query = {'youtube_url' : youtube_url, 'youtube_activate' : 7}
    youtube_document = collection_youtube_video.find_one(youtube_filter_query)
    youtube_index = youtube_document['youtube_index']
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

        user_filter_query = {'user_email_id': email_id, 'user_activate' : 7} #userid로 user찾는 필터쿼리 user_filter_query
        user_document = collection_user.find_one(user_filter_query)
        user_index = user_document['user_index']

        like_filter_query = {'user_index' : user_index, 'youtube_index' : youtube_index}
        like_document = collection_like.find_one(like_filter_query)

        if like_document :
            like_index = like_document['like_index']
            like_filter_query = {'like_index' : like_index}
            like_update_query = {'$set' : {'like_activate' : 0}}
            result = collection_like.update_one(like_filter_query, like_update_query)

            #좋아요 수 재 계산
            youtube_filter_query = {'youtube_index' : youtube_index, 'youtube_activate' : 7}
            youtube_update_query = {'$inc' : {'youtube_like' : -1}}
            result = collection_youtube_video.update_one(youtube_filter_query, youtube_update_query)

            return jsonify({'message' : 'like have been canceled'}), 200
        
#/watch/check-like로 라우팅
@watch_blueprint.route('check-like', methods = ['GET', 'POST'])
def check_like():
    cur_access_token = request.headers.get('Authorization')
    #print(cur_access_token)

    data = request.get_json()
    youtube_url = data.get('youtube_url', None)
    youtube_filter_query = {'youtube_url' : youtube_url, 'youtube_activate' : 7}
    youtube_document = collection_youtube_video.find_one(youtube_filter_query)
    youtube_index = youtube_document['youtube_index']

    verification_result = token_verification(cur_access_token)
    decoded_token = decode_token(cur_access_token)
    email_id = decoded_token['id'] # 토큰에서 email_id 추출
    user_filter_query = {'user_email_id': email_id, 'user_activate' : 7} #userid로 user찾는 필터쿼리 user_filter_query
    user_document = collection_user.find_one(user_filter_query)
    user_index = user_document['user_index']

    like_filter_query = {'youtube_index' : youtube_index, 'user_index' : user_index, 'like_activate' : 7}
    like_document = collection_like.find_one(like_filter_query)

    like_flag = 0 # 좋아요가 안된상태
    if like_document :
        like_flag = 1 # 이미 좋아요가 눌려있음

    return jsonify({'like_flag' : like_flag})