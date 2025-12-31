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
import numpy as np
#import matplotlib.pyplot as plt
import math
from gate import token_verification
from jwtfunction import decode_token, create_access_token, create_refresh_token

home_blueprint = Blueprint("home", __name__, url_prefix='/home')

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
collection_youtube_watching_data = db.youtube_watching_data
collection_youtube_inquiry = db.youtube_inquiry
collection_like = db.like


######################################################################################################################
def sqrt_func(x): #루트x * 0.05
	result = math.sqrt(x) * 0.05
	return result

def custom_function_hits(x): # 조회수 계산 함수
	temp = sqrt_func(x)
	ans = 5 * (1 + temp * np.log10(x))

	if ans > 28 : 
		ans = 28

	return ans

def custom_function_like(x): # 좋아요 수 계산 함수
	temp = sqrt_func(x)
	ans = 1 + temp * np.log10(x)

	if ans > 5.7 : 
		ans = 5.7

	return ans
######################################################################################################################


#distribution과 youtube_video합친 딕셔너리의 리스트 생성 메소드
def make_mixed_list():
    youtube_mixed_lists = [] # 빈 리스트 생성

    # youtube_video 콜렉션의 모든 도큐먼트 가져오기
    youtube_video_documents = collection_youtube_video.find({"youtube_activate" : 7})

    for youtube_video_document in youtube_video_documents : 
        list_youtube_index = youtube_video_document['youtube_index']

        distribution_filter_query = {"youtube_index" : list_youtube_index, 'distribution_activate' : 7}
        video_distribution_document = collection_video_distribution.find_one(distribution_filter_query)

        like_num_filter_query = {'youtube_index' : list_youtube_index, 'like_activate' : 7}
        like_num = collection_like.count_documents(like_num_filter_query)

        youtube_mixed_list = { # 두개의 도큐먼트를 합친 딕셔너리 생성
            'youtube_index' : list_youtube_index,
            'youtube_url' : youtube_video_document['youtube_url'],
            'youtube_real_url' : youtube_video_document['youtube_real_url'],
            'youtube_title' : youtube_video_document['youtube_title'],
            'youtube_channel' : youtube_video_document['youtube_channel'],
            'youtube_category' : youtube_video_document['youtube_category'],
            'youtube_create_date' : youtube_video_document['youtube_create_date'],
            'youtube_hits' : like_num,
            'youtube_like' : youtube_video_document['youtube_like'],
            'youtube_comment_num' : youtube_video_document['youtube_comment_num'],
            'watching_data_num' : video_distribution_document['watching_data_num'],
            'video_achivement_avg' : video_distribution_document['video_achivement_avg'],
            'emotion_statistics_avg_neutral' : video_distribution_document['emotion_statistics_avg']['neutral'],
            'emotion_statistics_avg_happy' : video_distribution_document['emotion_statistics_avg']['happy'],
            'emotion_statistics_avg_surprise' : video_distribution_document['emotion_statistics_avg']['surprise'],
            'emotion_statistics_avg_sad' : video_distribution_document['emotion_statistics_avg']['sad'],
            'emotion_statistics_avg_angry' : video_distribution_document['emotion_statistics_avg']['angry'],
            'most_emotion' : video_distribution_document['most_emotion'],
            'youtube_score' : 0,
            'youtube_rank' : 1
        }

        youtube_mixed_lists.append(youtube_mixed_list)
    return youtube_mixed_lists

######################################################################################################################

# 해당 딕셔너리 검색 메소드
def list_dic_find(diclist, ans_key, ans_value):
    idx = -1
    for i in range(len(diclist)) :
        if diclist[i][ans_key] == ans_value : # list[딕셔너리의 인덱스][딕셔너리의 키]
            idx = i # 찾는 딕셔너리의 인덱스
    return idx;

######################################################################################################################

#최근 10개의 영상 장르 및 감정 데이터 가산점
def cal_recently_data_score(user_id, youtube_mixed_lists) : 
    # 해당 유저의 최근 10개의 영상 시청 데이터 불러오기
    # user_index 검색
    user_filter_query = {'user_email_id': user_id, 'user_activate' : 7}
    #print(user_id)
    user_document = collection_user.find_one(user_filter_query)
    user_index = user_document['user_index']

    # watching_data_document에서 "date_create_time" 필드를 기준으로 내림차순으로 정렬
    watching_data_document = collection_youtube_watching_data.find({'user_index': user_index}).sort("date_create_time", -1)
	
    # 최대 10개의 도큐먼트를 가져오기
    recent_documents = list(watching_data_document.limit(10))

    for recent_document in recent_documents : # 최근 10개의 시청데이터마다 계산
        recent_emotion = recent_document['most_emotion'] # 해당 도큐먼트의 emotion
        recent_index = recent_document['youtube_index'] # 해당 도큐먼트의 youtube index

        # 해당 youtube의 평균 emotion비교
        recent_youtube_filter_query = {'youtube_index': recent_index} #해당 youtube index 검색

        this_idx = list_dic_find(youtube_mixed_lists, 'youtube_index', recent_index)

        recent_youtube_emotion = youtube_mixed_lists[this_idx]['most_emotion']

        # 유저가 느낀 most_emotion과 해당 영상의 most_emotion 통계가 같은 경우
        if (recent_emotion == recent_youtube_emotion) :
            for youtube_mixed_list in youtube_mixed_lists:
                if youtube_mixed_list['most_emotion'] == recent_emotion :
                    youtube_mixed_list['youtube_score'] += 4

        else :
            for youtube_mixed_list in youtube_mixed_lists:
                if youtube_mixed_list['most_emotion'] == recent_emotion :
                    youtube_mixed_list['youtube_score'] += 2
                if youtube_mixed_list['most_emotion'] == recent_youtube_emotion :
                    youtube_mixed_list['youtube_score'] += 2

        # 해당 영상 카테고리 리스트에서의 index 검색
        recent_category_index = list_dic_find(youtube_mixed_lists, 'youtube_index', recent_index)
        recent_category = youtube_mixed_lists[recent_category_index]['youtube_category'] # 해당 최근 영상의 유튜브 카테고리

        # 해당영상과 같은 카테고리인 유튜브 영상들 +4점 계산
        for youtube_mixed_list in youtube_mixed_lists:
            if youtube_mixed_list['youtube_category'] == recent_category :
                youtube_mixed_list['youtube_score'] += 4

######################################################################################################################

#유저 선호 카테고리 가산점
def cal_favorite_genre_score(user_id, youtube_mixed_lists) :
    user_filter_query = {'user_email_id': user_id, 'user_activate' : 7}
    user_document = collection_user.find_one(user_filter_query)

    user_favorite_1 = user_document['user_favorite_genre_1']
    user_favorite_2 = user_document['user_favorite_genre_2']
    user_favorite_3 = user_document['user_favorite_genre_3']

    for youtube_mixed_list in youtube_mixed_lists :
        this_category = youtube_mixed_list['youtube_category']
        if (this_category == user_favorite_1) or (this_category == user_favorite_2) or (this_category == user_favorite_3) :
            youtube_mixed_list['youtube_score'] += 5

######################################################################################################################

#페이스리뷰 조회수, 좋아요수 가산점
def view_score(youtube_mixed_lists) : 
    for youtube_mixed_list in youtube_mixed_lists :
        add_value = 0
        this_view = youtube_mixed_list['youtube_hits']
        this_like = youtube_mixed_list['youtube_like']
        if this_view != 0 :
            add_value += custom_function_hits(this_view)
        else :
            add_value += 0
        if this_view != 0 :
            add_value += custom_function_like(this_like)
        else : 
            add_value += 0

        youtube_mixed_list['youtube_score'] += add_value

######################################################################################################################

#무표정 비율에 따른 차등 점수 부여
def neutral_per_score(youtube_mixed_lists) :
    for youtube_mixed_list in youtube_mixed_lists :
        neutral_per = youtube_mixed_list['emotion_statistics_avg_neutral']
        sample_count = youtube_mixed_list['watching_data_num']
        if sample_count > 3 :
            if neutral_per >= 99.9 : #neutral 비율 99.9이상은 30점 감소
                youtube_mixed_list['youtube_score'] -= 30
            elif (99.9 > neutral_per) and (neutral_per >= 98) : #neutral 비율 98이상은 20점 감소
                youtube_mixed_list['youtube_score'] -= 20
            elif (98 > neutral_per) and (neutral_per >= 96) : #neutral 비율 96이상은 10점 감소
                youtube_mixed_list['youtube_score'] -= 10
            elif (96 > neutral_per) and (neutral_per >= 95) : #neutral 비율 95이상은 5점 감소
                youtube_mixed_list['youtube_score'] -= 5 
            else : # 나머지 3점 증가
                youtube_mixed_list['youtube_score'] += 3

######################################################################################################################

#유튜브 시청정도에 따른 차등 점수 부여
def achive_per_score(youtube_mixed_lists) :
    for youtube_mixed_list in youtube_mixed_lists :
        this_achivement = youtube_mixed_list['video_achivement_avg']

        if this_achivement >= 90 :
            youtube_mixed_list['youtube_score'] += 5
        if this_achivement < 10 :
            youtube_mixed_list['youtube_score'] -= 5

######################################################################################################################

#딕셔너리 리스트의 순위 정리
def ranking_dictionary(youtube_mixed_lists) :
    for youtube_mixed_list_i in youtube_mixed_lists :
        compare_score = youtube_mixed_list_i['youtube_score']
        origin_rank = youtube_mixed_list_i['youtube_rank']
        for youtube_mixed_list_j in youtube_mixed_lists :
            if(youtube_mixed_list_j['youtube_score'] > compare_score) :
                origin_rank += 1
        new_rank = origin_rank
        youtube_mixed_list_i['youtube_rank'] = new_rank

######################################################################################################################

#정렬된 리스트 바탕으로 필요한 데이터 생성
def modify_data(user_id, sorted_lists) :
    # 사용자가 본 영상 youtube_index 가져오기
    user_filter_query = {'user_id': user_id}
    youtube_index_documents = collection_youtube_inquiry.find(user_filter_query)

    if youtube_index_documents :
        #youtube_index만 뽑아서 youtube_index_list에 데이터 정리
        youtube_index_list = []
        for youtube_index_document in youtube_index_documents:
            youtube_index = youtube_index_document['youtube_index']
            youtube_index_list.append(youtube_index)

    new_data_list = []

    for sorted_list in sorted_lists :
        if youtube_index_documents :
            # 사용자가 본 영상이 sorted_lists 에 있으면 건너뛰기
            flag = 0
            for youtube_index in youtube_index_list :
                if sorted_list['youtube_index'] == youtube_index :
                    flag = 1
                    break
            if flag == 1:
                continue

        youtube_url = sorted_list['youtube_url']
        youtube_title = sorted_list['youtube_title']
        youtube_most_emotion = sorted_list['most_emotion']
        if youtube_most_emotion == 'neutral' :
            youtube_most_emotion_per = round(sorted_list['emotion_statistics_avg_neutral'] * 100, 2)
        elif youtube_most_emotion == 'happy' :
            youtube_most_emotion_per = round(sorted_list['emotion_statistics_avg_happy'] * 100, 2)
        elif youtube_most_emotion == 'angry' :
            youtube_most_emotion_per = round(sorted_list['emotion_statistics_avg_angry'] * 100, 2)
        elif youtube_most_emotion == 'sad' :
            youtube_most_emotion_per = round(sorted_list['emotion_statistics_avg_sad'] * 100, 2)
        elif youtube_most_emotion == 'surprise' :
            youtube_most_emotion_per = round(sorted_list['emotion_statistics_avg_surprise'] * 100, 2)
        elif youtube_most_emotion == 'None' :
            youtube_most_emotion_per = 'None'
        new_data_dict = {
            'youtube_url' : youtube_url,
            'youtube_title' : youtube_title,
            'youtube_most_emotion' : youtube_most_emotion,
            'youtube_most_emotion_per' : youtube_most_emotion_per
        }
        new_data_list.append(new_data_dict)

        if len(new_data_list) == 20:
            break
    return new_data_list

######################################################################################################################
#로그인 유저 / 유저 전용 추천 리스트, /home/user-customized-list로 라우팅
@home_blueprint.route('user-customized-list', methods = ['GET', 'POST'])
def user_customized_list():
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
        email_id = decoded_token['id']
        youtube_mixed_lists = make_mixed_list()
        cal_recently_data_score(email_id, youtube_mixed_lists) #최근 10개의 영상 장르 및 감정 데이터 가산점
        cal_favorite_genre_score(email_id, youtube_mixed_lists) #유저 선호 카테고리 가산점
        view_score(youtube_mixed_lists) #페이스리뷰 조회수, 좋아요수 가산점
        neutral_per_score(youtube_mixed_lists) #무표정 비율에 따른 차등 점수 부여
        achive_per_score(youtube_mixed_lists) #유튜브 시청정도에 따른 차등 점수 부여
        ranking_dictionary(youtube_mixed_lists) #점수에 따른 순위 정리
        # 리스트 안의 딕셔너리를 'youtube_rank'를 기준으로 정렬
        sorted_lists = sorted(youtube_mixed_lists, key=lambda x: x['youtube_rank'])
        new_data_list = modify_data(email_id ,sorted_lists)
        return jsonify(new_data_list), 200
    

######################################################################################################################
######################################################################################################################
######################################################################################################################


#모든 영상 리스트, /home/all-list로 라우팅
@home_blueprint.route('all-list', methods = ['POST', 'GET'])
def all_list():
    youtube_filter_query = {'youtube_activate' : 7}
    youtube_documents = collection_youtube_video.find(youtube_filter_query)

    youtube_url_list = []
    
    for youtube_document in youtube_documents :
        youtube_index = youtube_document['youtube_index']

        youtube_url = youtube_document['youtube_url']
        youtube_title = youtube_document['youtube_title']
        
        distribution_filter_query = {'youtube_index' : youtube_index}
        distribution_document = collection_video_distribution.find_one(distribution_filter_query)

        youtube_most_emotion = distribution_document['most_emotion']

        emotion_dict = {
            'neutral' : round(distribution_document['emotion_statistics_avg']['neutral'] * 100, 2),
            'happy' : round(distribution_document['emotion_statistics_avg']['happy'] * 100, 2),
            'surprise' : round(distribution_document['emotion_statistics_avg']['surprise'] * 100, 2),
            'angry' : round(distribution_document['emotion_statistics_avg']['angry'] * 100, 2),
            'sad' : round(distribution_document['emotion_statistics_avg']['sad'] * 100, 2),
            'None' : 'None'
        }
        
        youtube_most_emotion_per = emotion_dict[youtube_most_emotion]

        youtube_url_dict = {
            'youtube_url': youtube_url,
            'youtube_title': youtube_title,
            'youtube_most_emotion': youtube_most_emotion,
            'youtube_most_emotion_per': youtube_most_emotion_per
        }
        youtube_url_list.append(youtube_url_dict)

    return jsonify(youtube_url_list), 200


def cal_category_score(category_string, youtube_neutral_per, youtube_angry_per, youtube_happy_per, youtube_surprise_per, youtube_sad_per):
    category_score = 0
    if category_string == 'drama' :
        category_score += youtube_angry_per * 1 + youtube_happy_per * 1 + youtube_surprise_per * 1 + youtube_sad_per * 1
    elif category_string == 'eating' :
        category_score += youtube_angry_per * 1 + youtube_happy_per * 2 + youtube_surprise_per * 1
    elif category_string == 'travel' :
        category_score += youtube_angry_per * 1 + youtube_happy_per * 2 + youtube_surprise_per * 1
    elif category_string == 'cook' :
        category_score += youtube_neutral_per * 1 + youtube_happy_per * 2
    elif category_string == 'show' :
        category_score += youtube_sad_per * 1 + youtube_happy_per * 2 + youtube_surprise_per * 1
    elif category_string == 'information' :
        category_score += youtube_angry_per * 2 + youtube_neutral_per * 1 + youtube_surprise_per * 1
    elif category_string == 'fear' :
        category_score += youtube_surprise_per * 4
    elif category_string == 'game' :
        category_score += youtube_angry_per * 1 + youtube_happy_per * 1 + youtube_surprise_per * 1 + youtube_sad_per * 1
    elif category_string == 'sports' :
        category_score += youtube_happy_per * 1 + youtube_surprise_per * 3

    return category_score


def find_category_score_list(category_string):
    youtube_filter_query = {
        'youtube_activate': 7,
        'youtube_category': category_string
    }
    youtube_documents = collection_youtube_video.find(youtube_filter_query)

    # 도큐먼트에서 'youtube_index' 필드만 가져와서 만든 리스트
    youtube_index_list = [doc['youtube_index'] for doc in youtube_documents]

    distribution_score_lists = []

    for youtube_index in youtube_index_list : 
        category_score = 0
        distribution_filter_query = {'distribution_activate' : 7, 'youtube_index': youtube_index}
        distribution_document = collection_video_distribution.find_one(distribution_filter_query)

        youtube_filter_query = {'youtube_activate' : 7, 'youtube_index': youtube_index}
        youtube_document = collection_youtube_video.find_one(youtube_filter_query)

        # 1일 이내(8점), 1주일 이내(4점)
        current_date = datetime.now() # 현재날짜 불러오기 datetime형식
        youtube_create_date = youtube_document['youtube_create_date'] # youtube업로드 날짜
        # 날짜 차이 계산
        days_difference = (current_date - youtube_create_date).days

        if days_difference <= 1:
            category_score += 8
        elif days_difference <= 7:
            category_score += 4
        else :
            category_score += 4

        this_achivement = distribution_document['video_achivement_avg']

        if this_achivement >= 95 :
            category_score += 5
        elif this_achivement >= 90 :
            category_score += 3
        elif this_achivement >= 75 :
            category_score += 1
        else :
            category_score += 0

        youtube_neutral_per = distribution_document['emotion_statistics_avg']['neutral']
        youtube_happy_per = distribution_document['emotion_statistics_avg']['happy']
        youtube_angry_per = distribution_document['emotion_statistics_avg']['angry']
        youtube_sad_per = distribution_document['emotion_statistics_avg']['sad']
        youtube_surprise_per = distribution_document['emotion_statistics_avg']['surprise']

        category_score = cal_category_score(category_string, youtube_neutral_per, youtube_angry_per, youtube_happy_per, youtube_surprise_per, youtube_sad_per)

        distribution_score_list = {
            'youtube_index': youtube_index,
            'category_score': category_score
        }

        distribution_score_lists.append(distribution_score_list)

    sorted_distribution_score_lists = sorted(distribution_score_lists, key=lambda x: x['category_score'], reverse=True)

    return sorted_distribution_score_lists


def make_youtube_url_list(youtube_index_list):
    youtube_url_list = []
    for youtube_index in youtube_index_list :
        #해당하는 조건의 youtube_index를 가진 youtube 도큐먼트 검색
        youtube_filter_query = {'youtube_index': youtube_index, 'youtube_activate': 7}
        youtube_document = collection_youtube_video.find_one(youtube_filter_query)
        #해당하는 조건의 youtube_index를 가진 distribution 도큐먼트 검색
        distribution_filter_query = {'youtube_index': youtube_index, 'distribution_activate': 7}
        distribution_document = collection_video_distribution.find_one(distribution_filter_query)

        #필요한 데이터 불러오기
        youtube_url = youtube_document['youtube_url']
        youtube_title = youtube_document['youtube_title']
        youtube_index = youtube_document['youtube_index']
        youtube_most_emotion = distribution_document['most_emotion']
        if youtube_most_emotion != 'None' : 
            youtube_most_emotion_per = round(distribution_document['emotion_statistics_avg'][youtube_most_emotion] * 100, 2)
        else :
            youtube_most_emotion_per = 'None'

        youtube_url_dict = {
            'youtube_url': youtube_url,
            'youtube_title': youtube_title,
            'youtube_index' : youtube_index,
            'youtube_most_emotion': youtube_most_emotion,
            'youtube_most_emotion_per': youtube_most_emotion_per
        }

        youtube_url_list.append(youtube_url_dict)
    return youtube_url_list

def make_youtube_index_list(list_of_dictionary):
    youtube_index_list = []
    for dict in list_of_dictionary :
        youtube_index = dict['youtube_index']
        youtube_index_list.append(youtube_index)
    return youtube_index_list


def make_user_list(youtube_url_list, user_id):
    user_filter_query = {'user_id': user_id, 'inquiry_activate' : 7}
    youtube_index_documents = collection_youtube_inquiry.find(user_filter_query)

    if not youtube_index_documents :
        return youtube_url_list

    #youtube_index만 뽑아서 youtube_index_list에 데이터 정리
    inquiry_youtube_index_list = []
    for youtube_index_document in youtube_index_documents:
        inquiry_youtube_index = youtube_index_document['youtube_index']
        inquiry_youtube_index_list.append(inquiry_youtube_index)
    
    new_data_list = [] #새로 데이터를 저장할 리스트

    for youtube_url_dict in youtube_url_list :
        # 사용자가 본 영상이 sorted_lists 에 있으면 건너뛰기
        flag = 0
        for inquiry_youtube_index in inquiry_youtube_index_list : # 조회 list에서 youtube_index가 있는지 검색
            if youtube_url_dict['youtube_index'] == inquiry_youtube_index :
                flag = 1
                break
            if flag == 1:
                continue
                
        new_data_list.append(youtube_url_dict) # 없다면 list에 추가

    new_data_list = new_data_list[:20] #list에서 앞에서 최대 20개만 가져간다.

    return new_data_list
    

#첫번째 추천 리스트, /home/sports-list로 라우팅
@home_blueprint.route('sports-list', methods = ['POST', 'GET'])
def sports_list():
    category_string = 'sports'
    category_score_list = find_category_score_list(category_string) # category점수대로 저장된 리스트

    #list에서 youtube_index만 찾아서 youtube_index_list에 저장
    youtube_index_list = make_youtube_index_list(category_score_list)

    youtube_url_list = make_youtube_url_list(youtube_index_list)

    data = request.get_json()
    #print(data)
    user_categorization = data.get('user_categorization', None)
    cur_access_token = request.headers.get('Authorization')

    if user_categorization == 'non-user' :
        youtube_url_list = youtube_url_list[:20]
        return jsonify(youtube_url_list), 200
    
    elif user_categorization == 'user' :
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
            new_youtube_url_list = make_user_list(youtube_url_list, email_id)
            return jsonify(new_youtube_url_list), 200
######################################################################################################################
######################################################################################################################

#두번째 추천 리스트, /home/game-list로 라우팅
@home_blueprint.route('game-list', methods = ['POST', 'GET'])
def game_list():
    category_string = 'game'
    category_score_list = find_category_score_list(category_string) # category점수대로 저장된 리스트

    #list에서 youtube_index만 찾아서 youtube_index_list에 저장
    youtube_index_list = make_youtube_index_list(category_score_list)

    youtube_url_list = make_youtube_url_list(youtube_index_list)

    data = request.get_json()
    user_categorization = data.get('user_categorization', None)
    cur_access_token = request.headers.get('Authorization')

    if user_categorization == 'non-user' :
        youtube_url_list = youtube_url_list[:20]
        return jsonify(youtube_url_list), 200
    
    elif user_categorization == 'user' :
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
            new_youtube_url_list = make_user_list(youtube_url_list, email_id)
            return jsonify(new_youtube_url_list), 200
######################################################################################################################
######################################################################################################################

#세번째 추천 리스트, /home/fear-list로 라우팅
@home_blueprint.route('fear-list', methods = ['POST', 'GET'])
def fear_list():
    category_string = 'fear'
    category_score_list = find_category_score_list(category_string) # category점수대로 저장된 리스트

    #list에서 youtube_index만 찾아서 youtube_index_list에 저장
    youtube_index_list = make_youtube_index_list(category_score_list)

    youtube_url_list = make_youtube_url_list(youtube_index_list)

    data = request.get_json()
    user_categorization = data.get('user_categorization', None)
    cur_access_token = request.headers.get('Authorization')

    if user_categorization == 'non-user' :
        youtube_url_list = youtube_url_list[:20]
        return jsonify(youtube_url_list), 200
    
    elif user_categorization == 'user' :
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
            new_youtube_url_list = make_user_list(youtube_url_list, email_id)
            return jsonify(new_youtube_url_list), 200
######################################################################################################################
######################################################################################################################

#네번째 추천 리스트, /home/information-list로 라우팅
@home_blueprint.route('information-list', methods = ['POST', 'GET'])
def information_list():
    category_string = 'information'
    category_score_list = find_category_score_list(category_string) # category점수대로 저장된 리스트

    #list에서 youtube_index만 찾아서 youtube_index_list에 저장
    youtube_index_list = make_youtube_index_list(category_score_list)

    youtube_url_list = make_youtube_url_list(youtube_index_list)

    data = request.get_json()
    user_categorization = data.get('user_categorization', None)
    cur_access_token = request.headers.get('Authorization')

    if user_categorization == 'non-user' :
        youtube_url_list = youtube_url_list[:20]
        return jsonify(youtube_url_list), 200
    
    elif user_categorization == 'user' :
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
            new_youtube_url_list = make_user_list(youtube_url_list, email_id)
            return jsonify(new_youtube_url_list), 200
######################################################################################################################
######################################################################################################################

#다섯번째 추천 리스트, /home/show-list로 라우팅
@home_blueprint.route('show-list', methods = ['POST', 'GET'])
def show_list():
    category_string = 'show'
    category_score_list = find_category_score_list(category_string) # category점수대로 저장된 리스트

    #list에서 youtube_index만 찾아서 youtube_index_list에 저장
    youtube_index_list = make_youtube_index_list(category_score_list)

    youtube_url_list = make_youtube_url_list(youtube_index_list)

    data = request.get_json()
    user_categorization = data.get('user_categorization', None)
    cur_access_token = request.headers.get('Authorization')

    if user_categorization == 'non-user' :
        youtube_url_list = youtube_url_list[:20]
        return jsonify(youtube_url_list), 200
    
    elif user_categorization == 'user' :
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
            new_youtube_url_list = make_user_list(youtube_url_list, email_id)
            return jsonify(new_youtube_url_list), 200
######################################################################################################################
######################################################################################################################

#여섯번째 추천 리스트, /home/cook-list로 라우팅
@home_blueprint.route('cook-list', methods = ['POST', 'GET'])
def cook_list():
    category_string = 'cook'
    category_score_list = find_category_score_list(category_string) # category점수대로 저장된 리스트

    #list에서 youtube_index만 찾아서 youtube_index_list에 저장
    youtube_index_list = make_youtube_index_list(category_score_list)

    youtube_url_list = make_youtube_url_list(youtube_index_list)

    data = request.get_json()
    user_categorization = data.get('user_categorization', None)
    cur_access_token = request.headers.get('Authorization')

    if user_categorization == 'non-user' :
        youtube_url_list = youtube_url_list[:20]
        return jsonify(youtube_url_list), 200
    
    elif user_categorization == 'user' :
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
            new_youtube_url_list = make_user_list(youtube_url_list, email_id)
            return jsonify(new_youtube_url_list), 200
######################################################################################################################
######################################################################################################################

#일곱번째 추천 리스트, /home/travel-list로 라우팅
@home_blueprint.route('travel-list', methods = ['POST', 'GET'])
def travel_list():
    category_string = 'travel'
    category_score_list = find_category_score_list(category_string) # category점수대로 저장된 리스트

    #list에서 youtube_index만 찾아서 youtube_index_list에 저장
    youtube_index_list = make_youtube_index_list(category_score_list)

    youtube_url_list = make_youtube_url_list(youtube_index_list)

    data = request.get_json()
    user_categorization = data.get('user_categorization', None)
    cur_access_token = request.headers.get('Authorization')

    if user_categorization == 'non-user' :
        youtube_url_list = youtube_url_list[:20]
        return jsonify(youtube_url_list), 200
    
    elif user_categorization == 'user' :
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
            new_youtube_url_list = make_user_list(youtube_url_list, email_id)
            return jsonify(new_youtube_url_list), 200
######################################################################################################################
######################################################################################################################

#여덟번째 추천 리스트, /home/eating-list로 라우팅
@home_blueprint.route('eating-list', methods = ['POST', 'GET'])
def eating_list():
    category_string = 'eating'
    category_score_list = find_category_score_list(category_string) # category점수대로 저장된 리스트

    #list에서 youtube_index만 찾아서 youtube_index_list에 저장
    youtube_index_list = make_youtube_index_list(category_score_list)

    youtube_url_list = make_youtube_url_list(youtube_index_list)

    data = request.get_json()
    user_categorization = data.get('user_categorization', None)
    cur_access_token = request.headers.get('Authorization')

    if user_categorization == 'non-user' :
        youtube_url_list = youtube_url_list[:20]
        return jsonify(youtube_url_list), 200
    
    elif user_categorization == 'user' :
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
            new_youtube_url_list = make_user_list(youtube_url_list, email_id)
            return jsonify(new_youtube_url_list), 200
######################################################################################################################
######################################################################################################################

#아홉번째 추천 리스트, /home/drama-list로 라우팅
@home_blueprint.route('drama-list', methods = ['POST', 'GET'])
def drama_list():
    category_string = 'drama'
    category_score_list = find_category_score_list(category_string) # category점수대로 저장된 리스트

    #list에서 youtube_index만 찾아서 youtube_index_list에 저장
    youtube_index_list = make_youtube_index_list(category_score_list)

    youtube_url_list = make_youtube_url_list(youtube_index_list)

    data = request.get_json()
    user_categorization = data.get('user_categorization', None)
    cur_access_token = request.headers.get('Authorization')

    if user_categorization == 'non-user' :
        youtube_url_list = youtube_url_list[:20]
        return jsonify(youtube_url_list), 200
    
    elif user_categorization == 'user' :
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
            new_youtube_url_list = make_user_list(youtube_url_list, email_id)
            return jsonify(new_youtube_url_list), 200