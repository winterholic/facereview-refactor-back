from flask import request, Blueprint, jsonify
from datetime import datetime
from pymongo import MongoClient

#blueprint연결
register_blueprint = Blueprint("register", __name__, url_prefix='/register')

# MongoDB 연결 설정
client = MongoClient('mongodb://localhost:27017/')
db = client.FaceReview_Database
collection_youtube_recommend = db.youtube_recommend
collection_youtube_video = db.youtube_video

youtube_static_url = 'https://www.youtube.com/watch?v='

#영상추천기능, /register/recommend-register로 라우팅
@register_blueprint.route('recommend-register', methods = ['GET', 'POST'])
def update_recommend_list():
    data = request.get_json()
    youtube_url_id = data.get('youtube_url_id', None)
    youtube_real_url = youtube_static_url + youtube_url_id

    # 콜렉션 내의 도큐먼트 수 확인
    document_count = collection_youtube_recommend.count_documents({})
    index_max_value = document_count + 1

    collection_youtube_recommend.insert_one({
        "rec_index": index_max_value,
        "rec_url": youtube_url_id,
        "rec_real_url": youtube_real_url,
        "rec_check": 0, # rec_check 1 확인, rec_check 0 미확인
        "rec_date": datetime.utcnow(),
        "rec_activate": 7 # rec_activate 7 활성화, rec_activate 0 비활성화
    })

    return jsonify({'message' : 'YouTube video recommendation has been completed successfully'}), 200

#영상 추천받은 리스트(갱신 아직 안함) 정렬, /register/recommend-list로 라우팅
@register_blueprint.route('recommend-list', methods = ['GET'])
def recommend_list():
    uncheck_filter_query = {'rec_check' : 0, 'rec_activate' : 7}
    rec_documents = collection_youtube_recommend.find(uncheck_filter_query)

    rec_list = []

    index = 0
    for rec_document in rec_documents :
        youtube_url = rec_document['rec_url']
        youtube_filter_query = {'youtube_url' : youtube_url}
        youtube_document = collection_youtube_video.find_one(youtube_filter_query)
        if youtube_document :
            continue
        index += 1
        flag = 0
        for i in range(len(rec_list)) :
            if rec_list[i]['url'] == youtube_url :
                flag = 1
        if flag == 1 :
            continue
        data_dict = {
            'index' : index,
            'url' : rec_document['rec_url'],
            'full_url' : rec_document['rec_real_url']
        }
        rec_list.append(data_dict)
    
    return jsonify(rec_list), 200
"""

#관리자가 확인한 추천 리스트들 갱신 확인한 추천목록을 한번에 담아서 update, /register/check-list로 라우팅
@register_blueprint.route('check-list', methods = ['GET', 'POST'])
def check_list():
    data = request.get_json()
    url_list = data.get('url_list', None)
    
    for url_dict in url_list :
        youtube_url = url_dict['url']
        url_filter_query = {'rec_url' : youtube_url, 'rec_activate' : 7}
        url_update_query = {'$set' : {'rec_check' : 1}}
        collection_youtube_recommend.update_one(url_filter_query, url_update_query)
        
    return jsonify({'message' : 'The list has been updated'})
"""


#전체 영상 추천리스트 정렬, /register/all-recommend-list로 라우팅
@register_blueprint.route('all-recommend-list', methods = ['GET'])
def all_recommend_list():
    uncheck_filter_query = {'rec_activate' : 7}
    rec_documents = collection_youtube_recommend.find(uncheck_filter_query)

    rec_list = []
    index = 0
    for rec_document in rec_documents :
        index += 1
        data_dict = {
            'index' : index,
            'url' : rec_document['rec_url'],
            'full_url' : rec_document['rec_real_url']
        }
        rec_list.append(data_dict)
    
    return jsonify(rec_list), 200