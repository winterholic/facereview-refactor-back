from flask import Flask, render_template, Response, jsonify, Blueprint, request
from datetime import datetime, timedelta
from pymongo import MongoClient

#blueprint 연결
admin_blueprint = Blueprint("admin", __name__, url_prefix='/admin')

# MongoDB 연결 설정
client = MongoClient('mongodb://localhost:27017/')
db = client.FaceReview_Database
collection_user = db.user
collection_youtube_video = db.youtube_video
collection_video_distribution = db.video_distribution
collection_youtube_watching_data = db.youtube_watching_data
collection_youtube_watching_timeline = db.youtube_watching_timeline
collection_youtube_watching_timeline_data = db.youtube_watching_timeline_data

youtube_static_url = 'https://www.youtube.com/watch?v='


#유튜브 영상 등록, /admin/add-new-youtube-video로 라우팅
@admin_blueprint.route('add-new-youtube-video', methods = ['GET', 'POST'])
def add_new_youtube_video():
    # 콜렉션 내의 도큐먼트 수 확인
    document_count = collection_youtube_video.count_documents({})
    index_max_value = document_count + 1

    data = request.get_json()
    youtube_index = index_max_value
    youtube_url = data.get('youtube_url', None)
    youtube_real_url = youtube_url + youtube_static_url
    youtube_title = data.get('youtube_title', None)
    youtube_channel = data.get('youtube_channel', None)
    youtube_length_hour = data.get('youtube_length_hour', None)
    youtube_length_minute = data.get('youtube_length_minute', None)
    youtube_length_second = data.get('youtube_length_second', None)
    youtube_category = data.get('youtube_category', None)
    youtube_create_date = datetime.utcnow()
    youtube_hits = 0
    youtube_like = 0
    youtube_comment_num = 0
    youtube_activate = 7

    youtube_filter_query = {'youtube_url' : youtube_url, 'youtube_activate' : 7}
    youtube_document = collection_youtube_video.find_one(youtube_filter_query)

    if youtube_document :
        return jsonify({'message' : 'The video already exists'})

    collection_youtube_video.insert_one({
        'youtube_index' : youtube_index,
        'youtube_url' : youtube_url,
        'youtube_real_url' : youtube_real_url,
        'youtube_title' : youtube_title,
        'youtube_channel' : youtube_channel,
        'youtube_length_hour' : youtube_length_hour,
        'youtube_length_minute' : youtube_length_minute,
        'youtube_length_second' : youtube_length_second,
        'youtube_category' : youtube_category,
        'youtube_create_date' : youtube_create_date,
        'youtube_hits' : youtube_hits,
        'youtube_like' : youtube_like,
        'youtube_comment_num' : youtube_comment_num,
        'youtube_activate' : youtube_activate
    })

    distribution_filter_query = {"youtube_index" : youtube_index, 'distribution_activate' : 7}
    video_distribution_document = collection_video_distribution.find_one(distribution_filter_query)

    if not video_distribution_document:
        collection_video_distribution.insert_one({
        'youtube_index' : youtube_index,
        'watching_data_num' : 0,
        'video_achivement_avg' : float(0),
        'emotion_statistics_avg' : {
            'neutral' : float(0),
            'happy' : float(0),
            'surprise' : float(0),
            'sad' : float(0),
            'angry' : float(0)
        },
        'emotion_statistics_score' : {
            'neutral' : float(0),
            'happy' : float(0),
            'surprise' : float(0),
            'sad' : float(0),
            'angry' : float(0)
        },
        'most_emotion' : 'None',
        'distribution_activate' : 7
        })

    return jsonify({'message' : 'The YouTube video has been added'}), 200


#임시로 현재 데이터베이스의 distribution_document생성 api, /admin/create-distribution로 라우팅
@admin_blueprint.route('create-distribution', methods = ['GET', 'POST'])
def create_distribution():
    youtube_documents = collection_youtube_video.find()

    for youtube_document in youtube_documents :
        youtube_index = youtube_document['youtube_index']

        distribution_filter_query = {'youtube_index' : youtube_index}
        distribution_document = collection_video_distribution.find_one(distribution_filter_query)

        if not distribution_document :
            collection_video_distribution.insert_one({
        'youtube_index' : youtube_index,
        'watching_data_num' : 0,
        'video_achivement_avg' : float(0),
        'emotion_statistics_avg' : {
            'neutral' : float(0),
            'happy' : float(0),
            'surprise' : float(0),
            'sad' : float(0),
            'angry' : float(0)
        },
        'emotion_statistics_score' : {
            'neutral' : float(0),
            'happy' : float(0),
            'surprise' : float(0),
            'sad' : float(0),
            'angry' : float(0)
        },
        'most_emotion' : 'None',
        'distribution_activate' : 7
        })
    return jsonify({'message' : 'create distribution'}), 200





#유저 회원탈퇴 시나리오
#1. 먼저 유저 테이블에서 user_index,user_email_id 값 찾고, user_activate : 0
#2. comment 테이블에서 user_index검색해서 comment_activate 0 , youtube_video 테이블에서 youtubue_index검색해서 youtube_comment_num -1
#3. inquiry 테이블에서 user_id검색해서 inquiry_activate 0, youtube_video 테이블에서 youtube_index 검색해서 youtube_hits -1
#4. youtube_watching_data 테이블에서 user_index검색해서 watching_data_activate 0
#ㄴ watching_data_index(youtube_watching_timeline갱신을 위함), youtube_index 값 찾기
#5. youtube_watching_timeline테이블에서 watching_data_index검색해서, youtube_watching_timeline_activate 0
#ㄴ youtube_watching_timeline의 정리 데이터 = youtube_watching_data이기 때문
#6. timeline_emotion_num에서 youtube_index검색해서 재연산
#ㄴ youtube_index바탕으로 youtube_watching_data검색해서 재연산
#7. timeline_emotion_num을 재연산 하는 과정에서 timeline_emotion_per,timeline_emotion_most 재연산
#8. 재연산된 데이터들을 바탕으로 youtube_distribution 재연산
#ㄴ video_achivement_avg - youtube_index바탕으로 youtube_watching_data테이블에서 watching_achivement_per로 재계산
#ㄴ emotion_statistics_avg - youtube_index바탕으로 youtube_watching_data테이블에서 emotion_statistics_per로 재계산
#ㄴ emotion_statistics_score - 재계산된 emotion_statistics_avg 바탕으로 재계산, neutral*1, happy*5, surprise*10, sad*7, angry*7
#ㄴ run.py의 distribution_update 참고






#유저 시청기록 제거 시나리오



#문제있는데이터베이스 제거 api, /admin/delete-trash-watching로 라우팅
@admin_blueprint.route('delete-trash-watching', methods = ['GET', 'POST'])
def delete_trash_watching():
    watching_data_filter_query = {'watching_achivement_per' : 'None'}
    trash_documents = collection_youtube_watching_data.find(watching_data_filter_query)

    for trash_document in trash_documents :
        watching_data_index = trash_document['watching_data_index']
        watching_filter_query = {'watching_data_index' : watching_data_index}
        result1 = collection_youtube_watching_data.delete_one(watching_filter_query)
        result2 = collection_youtube_watching_timeline.delete_one(watching_filter_query)
        result3 = collection_youtube_watching_timeline.delete_one(watching_filter_query)