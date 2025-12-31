# -*- coding: utf-8 -*-
import xml.etree.ElementTree as elemTree
from flask import Flask, render_template, Response, jsonify, Blueprint, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from datetime import datetime, timedelta
import random
import ssl

from gate import gate_blueprint
from home import home_blueprint
from mypage import mypage_blueprint
from watch import watch_blueprint
from register import register_blueprint
from admin import admin_blueprint

from PIL import Image
from tensorflow import keras
import base64
import numpy as np
import io
import cvlib as cv
import cv2
from pymongo import MongoClient
from datetime import datetime, timedelta

from jwtfunction import decode_token, create_access_token, create_refresh_token


app = Flask(__name__)
CORS(app)


# load model
model = keras.models.load_model('model.h5')

# emotion list
emotion = ["happy", "surprise", "angry", "sad", "neutral"] 

# MongoDB 연결 설정
client = MongoClient('mongodb://localhost:27017/')
db = client.FaceReview_Database
collection_user = db.user
collection_youtube_video = db.youtube_video
collection_video_distribution = db.video_distribution
collection_youtube_watching_data = db.youtube_watching_data
collection_youtube_inquiry = db.youtube_inquiry
collection_youtube_watching_timeline = db.youtube_watching_timeline
collection_youtube_watching_timeline_data = db.youtube_watching_timeline_data
collection_timeline_emotion_num = db.timeline_emotion_num
collection_timeline_emotion_per = db.timeline_emotion_per
collection_timeline_emotion_most = db.timeline_emotion_most



# XML 파일 경로 설정
xml_file_path = r'/home/cdserver1201/facereview/keys.xml'
#xml_file_path = r'C:\Users\Administrator\Desktop\liveserver\keys.xml'
# XML 파일 파싱
tree = elemTree.parse(xml_file_path)
# XML 요소 찾기
secret_key_element = tree.find('.//string[@name="secret_key"]')
# secret_key 값을 가져오고 설정
if secret_key_element is not None:
    secretkey = secret_key_element.text
    app.config['SECRET_KEY'] = secretkey
else:
    print("XML 파일에서 'secret_key'를 찾을 수 없습니다.")


#현재 시간
now = str(datetime.utcnow)


#gate_blueprint
app.register_blueprint(gate_blueprint)
#home_blueprint
app.register_blueprint(home_blueprint)
#mypage_blueprint
app.register_blueprint(mypage_blueprint)
#watch_blueprint
app.register_blueprint(watch_blueprint)
#register_blueprint
app.register_blueprint(register_blueprint)
#admin_blueprint
app.register_blueprint(admin_blueprint)




#--------------------------------------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------------------------------------


def make_user_index_list():
    user_list = []
    user_documents = collection_user.find()
    for user_document in user_documents :
        user_index = user_document['user_index']
        user_id = user_document['user_email_id']
        user_dict = {
            'user_index' : user_index,
            'user_id' : user_id
        }
        user_list.append(user_dict)
    return user_list

user_list = make_user_index_list()

# 해당 딕셔너리 검색 메소드
def list_dic_find(diclist, ans_key, ans_value):
    idx = -1
    for i in range(len(diclist)) :
        if diclist[i][ans_key] == ans_value : # list[딕셔너리의 인덱스][딕셔너리의 키]
            idx = i # 찾는 딕셔너리의 인덱스
    return idx;

socketio = SocketIO(app, cors_allowed_origins="*")

# framedata를 임시로 보관할 리스트를 담을 클래스
class UserFrameData:
    user_data_list = []  # 리스트들을 보관할 리스트

    def __init__(self, socket_id):
        self.socket_id = socket_id
        self.data_list = []

    @classmethod
    def add_data(cls, socket_id, youtube_index, user_index, data_dict):
        # 클래스 메서드를 통해 데이터 추가
        for instance in cls.user_data_list:
            if instance.socket_id == socket_id:  # socket_id와 같은 인스턴스가 있다면
                instance.data_list.append(data_dict)  # 해당 인스턴스에 딕셔너리 추가
                return
        # 해당 socket_id를 가진 인스턴스가 없으면 새로운 인스턴스를 생성하고 데이터 추가
        new_instance = cls(socket_id)
        temp_dict = {
            'youtube_index' : youtube_index,
            'user_index' : user_index
        }
        new_instance.data_list.append(temp_dict)
        new_instance.data_list.append(data_dict)
        cls.user_data_list.append(new_instance)

    @classmethod
    def get_user_youtube_index(cls, socket_id) : 
        index_dict = {}
        for instance in cls.user_data_list:
            if instance.socket_id == socket_id :
                for data_dict in instance.data_list :
                    user_index = data_dict['user_index']
                    youtube_index = data_dict['youtube_index']
                    index_dict['user_index'] = user_index
                    index_dict['youtube_index'] = youtube_index
                    break
        return index_dict
    """
    @classmethod
    def print_list_data(cls, socket_id) :
        for instance in cls.user_data_list:
            if instance.socket_id == socket_id:
                for data_dict in instance.data_list:
                    print(data_dict)
    """
    @classmethod
    def update_timeline_dictionary(cls, socket_id, initial_timeline_dictionary, initial_timeline_data_dictionary):
        print('구간2-2-1')
        for instance in cls.user_data_list:
            if instance.socket_id == socket_id:
                print('구간2-2-2')
                cnt = 0
                for data_dict in instance.data_list:
                    #print(data_dict)
                    if cnt == 0 :
                        print('구간2-2-3')
                        cnt += 1
                        continue
                    key_name = data_dict['youtube_running_time']
                    print(key_name)
                    if(key_name == '0:00:00') :
                        continue
                    value_name = data_dict['most_emotion']
                    initial_timeline_dictionary[key_name] = value_name
                    #print(initial_timeline_dictionary[key_name])

                    value_name_2 = data_dict['happy_per']
                    initial_timeline_data_dictionary[key_name]['happy'] = value_name_2

                    value_name_3 = data_dict['neutral_per']
                    initial_timeline_data_dictionary[key_name]['neutral'] = value_name_3

                    value_name_4 = data_dict['angry_per']
                    initial_timeline_data_dictionary[key_name]['angry'] = value_name_4

                    value_name_5 = data_dict['surprise_per']
                    initial_timeline_data_dictionary[key_name]['surprise'] = value_name_5

                    value_name_6 = data_dict['sad_per']
                    initial_timeline_data_dictionary[key_name]['sad'] = value_name_6

                    print(key_name, value_name, value_name_2, value_name_3, value_name_4, value_name_5, value_name_6)

                instance.data_list = []  # 해당 데이터 모두 사용 후 비우기
                cls.user_data_list.remove(instance)  # 딕셔너리가 비어있는 리스트 제거

    


def search_most_emotion(happy_per, surprise_per, angry_per, sad_per, neutral_per):
    emotions = {
        'happy': happy_per, 
        'surprise': surprise_per, 
        'angry': angry_per, 
        'sad': sad_per, 
        'neutral': neutral_per
        }
    most_emotion = max(emotions, key=emotions.get)
    return most_emotion

#감점 분석 메소드
def analysis_emotion(youtube_running_time, string_frame_data):
    # imgdata
    imgdata = string_frame_data
    imgdata = base64.b64decode(imgdata) # base64 to image

    # image open
    image = Image.open(io.BytesIO(imgdata))
    image = np.array(image)

     #detect face and crop
    faces, conf = cv.detect_face(image)
    for (x, y, x2, y2) in faces:
        cropped_image = image[y:y2, x:x2]
    resized_face = cv2.resize(cropped_image, (96,96))
    gray_face = cv2.cvtColor(resized_face, cv2.COLOR_BGR2GRAY)

    img = gray_face

    # image normalization
    img = img / 255

    img = img.reshape(96, 96, 1)
    img = np.expand_dims(img, axis=0)

    #predict
    pred = model.predict(img, verbose=0)

    new_pred_data = [round(x * 100, 2) for x in pred[0]]

    #print(new_pred_data)

    most_emotion = search_most_emotion(new_pred_data[0], new_pred_data[1], new_pred_data[2], new_pred_data[3], new_pred_data[4])

    frame_emotion_data_dict = {
        'most_emotion' : most_emotion,
        'youtube_running_time' : youtube_running_time,
        'happy' : new_pred_data[0],
        'surprise' : new_pred_data[1],
        'angry' : new_pred_data[2],
        'sad' : new_pred_data[3],
        'neutral' : new_pred_data[4]
    }

    #print(frame_emotion_data_dict)

    return frame_emotion_data_dict



# 소켓 통신 후 데이터 전송 후 데이터 베이스 갱신 시나리오
# 1. 클라이언트로부터 소켓을 통해 메세지를 전송받는다.
# 이 때 메세지에는 유저의 토큰(만료된 토큰도 가능), 해당 유튜브 시간, 해당 frame의 스트링data, 유튜브의 인덱스(미리 서버에서 보내준다.)
# 2. 서버에서 model.h5를 불러와서 해당 frame의 감정정보를 분석한다.
# 이때, 의문점 : 우리 모델은 옆모습(정면 응시가 아닌 사진) 등에서도 취약한 모습을 보였는데, 유저가 잠시 이탈하였을 때도 캠이 계속 연결되거나 할 때도
# 감정 데이터로 분석될 것 같다. 이때의 오류나 예외처리가 생긴다면 처리해줘야하고, 보완점이 있으면 추가해야한다.
# 3. 분석한 감정 정보를 파이썬의 리스트에 저장해두고, 클라이언트로 전송해준다.
# 이때 클라이언트로 전송하는 정보에는 최다 감정, 각 감정의 수치, 유튜브 러닝타임을 보내준다.
# 파이썬의 리스트에 저장할 감정 정보는 유저인덱스, 유튜브인덱스, 유튜브 러닝타임, 최다감정을 저장한다.
# 4. 클라이언트가 소켓 연결 종료를 알려오면 데이터베이스에 갱신을 시작한다.



#--------------------------------------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------------------------------------
# 클라이언트 메세지 분석 후 데이터 전송 이벤트, 소켓 이벤트에서는 토큰 검증을 진행하지 않는다.
# watching_data_index를 받기 때문에, user정보가 필요가 없어서 토큰 검증을 진행하지 않아도 된다.
@socketio.on('client_message')
def handle_client_message(message):
    #print('***************************************************************************************')
    socket_id = request.sid
    youtube_running_time = message['youtube_running_time']
    string_frame_data = message['string_frame_data']
    youtube_index = message['youtube_index']
    user_token = message['cur_access_token']

    decoded_token = decode_token(user_token)
    user_id = decoded_token['id']

    user_index_idx = list_dic_find(user_list, 'user_id', user_id)
    user_index = user_list[user_index_idx]['user_index']

    frame_emotion_data_dict = analysis_emotion(youtube_running_time, string_frame_data) # 실시간 감정 분석 데이터

    #print('************************분석완료*********************************')

    # 해당 러닝타임에서의 유저들의 평균데이터도 불러오기
    timeline_emotion_filter_query = {'youtube_index' : youtube_index, 'timeline_emotion_most_activate' : 7}
    timeline_emotion_document = collection_timeline_emotion_most.find_one(timeline_emotion_filter_query)

    timeline_emotion_filter_query = {'youtube_index' : youtube_index, 'timeline_emotion_per_activate' : 7}
    timeline_per_document = collection_timeline_emotion_per.find_one(timeline_emotion_filter_query)

    if not timeline_emotion_document :
        emotion_data = 'neutral'
        neutral_per_data = round(100, 0)
        angry_per_data = float(0)
        happy_per_data = float(0)
        surprise_per_data = float(0)
        sad_per_data = float(0)
    else : 
        emotion_data = timeline_emotion_document[youtube_running_time]
        neutral_per_data = round(timeline_per_document[youtube_running_time]['neutral']*100, 2)
        angry_per_data = round(timeline_per_document[youtube_running_time]['angry']*100, 2)
        happy_per_data = round(timeline_per_document[youtube_running_time]['happy']*100, 2)
        surprise_per_data = round(timeline_per_document[youtube_running_time]['surprise']*100, 2)
        sad_per_data = round(timeline_per_document[youtube_running_time]['sad']*100, 2)

    #frame_emotion_data_dict에 유저들의 평균데이터 추가
    frame_emotion_data_dict['youtube_emotion_data'] = emotion_data
    frame_emotion_data_dict['youtube_emotion_neutral_per'] = neutral_per_data
    frame_emotion_data_dict['youtube_emotion_angry_per'] = angry_per_data
    frame_emotion_data_dict['youtube_emotion_happy_per'] = happy_per_data
    frame_emotion_data_dict['youtube_emotion_surprise_per'] = surprise_per_data
    frame_emotion_data_dict['youtube_emotion_sad_per'] = sad_per_data

    emotion_data_dict = {
        'youtube_running_time' : youtube_running_time,
        'most_emotion' : frame_emotion_data_dict['most_emotion'],
        'happy_per' : frame_emotion_data_dict['happy'],
        'sad_per' : frame_emotion_data_dict['sad'],
        'angry_per' : frame_emotion_data_dict['angry'],
        'neutral_per' : frame_emotion_data_dict['neutral'],
        'surprise_per' : frame_emotion_data_dict['surprise']
    }

    if emotion_data == 'None' :
        frame_emotion_data_dict['youtube_emotion_neutral_per'] = round(100, 0)
        frame_emotion_data_dict['youtube_emotion_angry_per'] = float(0)
        frame_emotion_data_dict['youtube_emotion_happy_per'] = float(0)
        frame_emotion_data_dict['youtube_emotion_surprise_per'] = float(0)
        frame_emotion_data_dict['youtube_emotion_sad_per'] = float(0)
    
    frame_emotion_data_dict['socket_id'] = socket_id
    frame_emotion_data_dict['user_index'] = user_index

    # 데이터 리스트에 임시로 저장
    UserFrameData.add_data(socket_id, youtube_index, user_index, emotion_data_dict)

    #print('**********************************전송전***************************************')

    return frame_emotion_data_dict
#--------------------------------------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------------------------------------


def update_watching_data_table(socket_id, watching_data_index):
    print('watching_data_table진입')
    #먼저 youtube_watching_timeline 테이블에 도큐먼트 생성하기 위해 필요한 데이터 불러오기
    watching_data_filter_query = {'watching_data_index' : watching_data_index, 'watching_data_activate' : 7}
    watching_data_document = collection_youtube_watching_data.find_one(watching_data_filter_query) # watching_data도큐먼트에서 youtube_index와 user_index 불러오기
    youtube_index = watching_data_document['youtube_index'] 
    user_index = watching_data_document['user_index']

    youtube_filter_query = {'youtube_index' : youtube_index, 'youtube_activate' : 7} #유튜브 영상 길이를 찾기 위한 메소드
    youtube_document = collection_youtube_video.find_one(youtube_filter_query)
    youtube_length_hour = youtube_document['youtube_length_hour']
    youtube_length_minute = youtube_document['youtube_length_minute']
    youtube_length_second = youtube_document['youtube_length_second']

    #youtube_watching_timeline 테이블에 도큐먼트 생성
    initial_watching_timeline_data = {
        'watching_data_index' : watching_data_index,
        'youtube_index' : youtube_index,
        'user_index' : user_index,
        'watching_timeline_activate' : 7
    }
    #collection_youtube_watching_timeline.insert_one(initial_watching_timeline_data)

    #youtube_watching_timeline_data 테이블에 도큐먼트 생성
    #collection_youtube_watching_timeline_data.insert_one(initial_watching_timeline_data)

    print('작동1')

    # 시작 시간
    start_time = timedelta(seconds=1)

    # 종료 시간
    end_time = timedelta(hours=youtube_length_hour, minutes=youtube_length_minute, seconds=youtube_length_second)

    # 시간 
    time_interval = timedelta(seconds=1)

    # 성취도 계산, 생각해보니까 성취도가 100이 넘지 못할거 같네 아닌가... db만 안겹치고 100넘나?
    max_achivement_num = youtube_length_second + youtube_length_minute*60 + youtube_length_hour*360
    watching_achivement_num = 0
    for instance in UserFrameData.user_data_list:
        if instance.socket_id == socket_id :
            for data_dict in instance.data_list :
                watching_achivement_num += 1
    watching_achivement_per = round(watching_achivement_num / max_achivement_num, 3)

    #print('구간1')

    alpha_point = watching_achivement_num*0.1
    user_filter_query = {'user_index' : user_index, 'user_activate' : 7}
    user_update_query = {'$inc' : {'user_point' : +alpha_point}}
    alpha_point = round(alpha_point, 1)
    collection_user.update_one(user_filter_query,user_update_query)
    

    #print('구간2')
    #print(alpha_point)

    print('작동2')

    #업데이트를 위한 딕셔너리
    initial_timeline_dictionary = {
        'watching_data_index' : watching_data_index,
        'youtube_index' : youtube_index,
        'user_index' : user_index,
        'watching_timeline_activate' : 7
    }
    initial_timeline_data_dictionary = {
        'watching_data_index' : watching_data_index,
        'youtube_index' : youtube_index,
        'user_index' : user_index,
        'watching_timeline_activate' : 7
    }

    # 시작 시간
    start_time = timedelta(seconds=1)

    # 종료 시간
    end_time = timedelta(hours=youtube_length_hour, minutes=youtube_length_minute, seconds=youtube_length_second)

    print('작동2-1')

    #print('구간3')

    # 시간 
    time_interval = timedelta(seconds=1)

    # youtube_running_time에 해당하는 이름의 키를 딕셔너리에 생성 벨류는 None으로 저장
    while start_time <= end_time:
        formatted_time = str(start_time)[0:10] #시간데이터 문자열 변환 00:00:00과같은 형식
        initial_timeline_dictionary[formatted_time] = 'None'
        initial_timeline_data_dictionary[formatted_time] = {
            'happy' : float(0),
            'neutral' : float(0),
            'surprise' : float(0),
            'angry' : float(0),
            'sad' : float(0)
        }
        start_time += time_interval

    #print('구간4')

    print('작동2-2')

    # 리스트에 저장해둔 데이터에 해당하는 time의 키를 가진 딕셔너리가 있다면 벨류값에 감정 저장
    UserFrameData.update_timeline_dictionary(socket_id, initial_timeline_dictionary, initial_timeline_data_dictionary)

    print('작동2-3')

    collection_youtube_watching_timeline.insert_one(initial_timeline_dictionary)
    collection_youtube_watching_timeline_data.insert_one(initial_timeline_data_dictionary)

    print('작동2-4')

    #youtube_watching_timeline테이블 필터쿼리
    #timeline_filter_query = {'watching_data_index' : watching_data_index, 'watching_timeline_activate' : 7}
    #timeline_update_query = {'$set': initial_timeline_dictionary}

    # 업데이트 수행
    #collection_youtube_watching_timeline.update_one(timeline_filter_query, timeline_update_query)

    #timeline_data_filter_query = {'watching_data_index' : watching_data_index, 'watching_timeline_activate' : 7}
    #timeline_update_query = {'$set': initial_timeline_data_dictionary}

    # 업데이트 수행
    #collection_youtube_watching_timeline_data.update_one(timeline_data_filter_query, timeline_update_query)

    # emotion_statistics_per계산을 위한 emotion_statistics_num 찾기
    happy_num = 0
    surprise_num = 0
    angry_num = 0
    sad_num = 0
    neutral_num = 0

    #개수 갱신
    for key, value in initial_timeline_dictionary.items():
        if value == 'happy':
            happy_num += 1
        elif value == 'surprise':
            surprise_num += 1
        elif value == 'angry' :
            angry_num += 1
        elif value == 'sad' :
            sad_num += 1
        elif value == 'neutral' :
            neutral_num += 1

    print('작동3')

    #print(happy_num, surprise_num, angry_num, sad_num, neutral_num)

    # 총합 감정데이터 개수
    sum_emotion_num = happy_num + surprise_num + angry_num + sad_num + neutral_num
    if happy_num != 0 :
        happy_per = round(happy_num / sum_emotion_num, 2)
    else :
        happy_per = float(0)
    if surprise_num != 0 :
        surprise_per = round(surprise_num / sum_emotion_num, 2)
    else :
        surprise_per = float(0)
    if angry_num != 0 :
        angry_per = round(angry_num / sum_emotion_num, 2)
    else :
        angry_per = float(0)
    if sad_num != 0 :
        sad_per = round(sad_num / sum_emotion_num, 2)
    else :
        sad_per = float(0)
    if neutral_num != 0 :
        neutral_per = round(neutral_num / sum_emotion_num, 2)
    else :
        neutral_per = float(0)

    #print(happy_per, surprise_per, angry_per, sad_per, neutral_per)

    # mostemotion을 찾기 위한 감정데이터 점수 계산
    happy_score = round(happy_per * 3, 2)
    surprise_score = round(surprise_per * 4, 2)
    angry_score = round(angry_per * 3, 2)
    sad_score = round(sad_per * 3, 2)
    neutral_score = round(neutral_per * 2, 2)

    emotion_scores = {
    'happy': happy_score,
    'surprise': surprise_score,
    'angry': angry_score,
    'sad': sad_score,
    'neutral': neutral_score
    }

    print('작동4')

    most_emotion = max(emotion_scores, key=emotion_scores.get)

    watching_data_update_dictionary = {
        'watching_achivement_per' : watching_achivement_per,
        'emotion_statistics_per': {
        'neutral': neutral_per,
        'happy': happy_per,
        'surprise': surprise_per,
        'sad': sad_per,
        'angry': angry_per
        },
        'emotion_statistics_score': {
        'neutral': neutral_score,
        'happy': happy_score,
        'surprise': surprise_score,
        'sad': sad_score,
        'angry': angry_score
        },
        'most_emotion' : most_emotion
    }

    #print(watching_data_update_dictionary)

    #youtube_watching_data테이블 필터쿼리
    watchingdata_filter_query = {'watching_data_index' : watching_data_index, 'watching_data_activate' : 7}
    watchingdata_update_query = {'$set': watching_data_update_dictionary}

    # 업데이트 수행
    collection_youtube_watching_data.update_one(watchingdata_filter_query, watchingdata_update_query)

    print('작동5')

    #timeline_emotion_num, timeline_emotion_per, timeline_emotion_most 테이블 데이터 갱신
    #갱신 시에 필요한 도큐먼트가 존재하지 않는다면 생성
    update_timeline_emotion_data(socket_id, watching_data_index)


def update_timeline_emotion_data(socket_id, watching_data_index):
    print('watching_timeline_emotion_data진입')
    #먼저 youtube_watching_timeline 테이블에 도큐먼트 생성하기 위해 필요한 데이터 불러오기
    watching_data_filter_query = {'watching_data_index' : watching_data_index, 'watching_data_activate' : 7}
    watching_data_document = collection_youtube_watching_data.find_one(watching_data_filter_query) # watching_data도큐먼트에서 youtube_index와 user_index 불러오기
    youtube_index = watching_data_document['youtube_index']
    #print(watching_data_index, youtube_index)

    youtube_filter_query = {'youtube_index' : youtube_index, 'youtube_activate' : 7} #유튜브 영상 길이를 찾기 위한 필터 쿼리
    youtube_document = collection_youtube_video.find_one(youtube_filter_query)

    youtube_length_hour = youtube_document['youtube_length_hour']
    youtube_length_minute = youtube_document['youtube_length_minute']
    youtube_length_second = youtube_document['youtube_length_second']

    # 각 타임라인 별 감정 데이터 개수를 저장할 테이블
    timeline_num_filter_query = {'youtube_index' : youtube_index, 'timeline_emotion_num_activate' : 7}
    timeline_num_document = collection_timeline_emotion_num.find_one(timeline_num_filter_query)

    # 각 타임라인 별 감정 분포를 저장할 테이블
    timeline_per_filter_query = {'youtube_index' : youtube_index, 'timeline_emotion_per_activate' : 7}
    timeline_per_document = collection_timeline_emotion_per.find_one(timeline_per_filter_query)

    # 각 타임라인 별 최다 감정을 저장할 테이블
    timeline_most_filter_query = {'youtube_index' : youtube_index, 'timeline_emotion_most_activate' : 7}
    timeline_most_document = collection_timeline_emotion_most.find_one(timeline_most_filter_query)

    # timeline_num_document가 존재하지 않는 경우
    if not timeline_num_document :
        #새로운 도큐먼트 생성
        timeline_num_dict = {
            'youtube_index' : youtube_index,
            'timeline_emotion_num_activate' : 7
        }
        # 시작 시간
        start_time = timedelta(seconds=1)

        # 종료 시간
        end_time = timedelta(hours=youtube_length_hour, minutes=youtube_length_minute, seconds=youtube_length_second)

        # 시간 
        time_interval = timedelta(seconds=1)

        # youtube_running_time에 해당하는 이름의 키를 딕셔너리에 생성 벨류는 None으로 저장
        while start_time <= end_time:
            formatted_time = str(start_time)[0:10] #시간데이터 문자열 변환 00:00:00과같은 형식
            temp_dict = {
                'happy' : 0,
                'surprise' : 0,
                'angry' : 0,
                'sad' : 0,
                'neutral' :0
            }
            timeline_num_dict[formatted_time] = temp_dict
            start_time += time_interval
        
        collection_timeline_emotion_num.insert_one(timeline_num_dict)
        timeline_num_document = collection_timeline_emotion_num.find_one(timeline_num_filter_query)

    # timeline_per_document가 존재하지 않는 경우
    if not timeline_per_document :
        timeline_per_dict = {
            'youtube_index' : youtube_index,
            'timeline_emotion_per_activate' : 7
        }

        # 시작 시간
        start_time = timedelta(seconds=1)

        # 종료 시간
        end_time = timedelta(hours=youtube_length_hour, minutes=youtube_length_minute, seconds=youtube_length_second)

        # 시간 
        time_interval = timedelta(seconds=1)

        # youtube_running_time에 해당하는 이름의 키를 딕셔너리에 생성 벨류는 None으로 저장
        while start_time <= end_time:
            formatted_time = str(start_time)[0:10] #시간데이터 문자열 변환 00:00:00과같은 형식
            temp_dict = {
                'happy' : float(0),
                'surprise' : float(0),
                'angry' : float(0),
                'sad' : float(0),
                'neutral' :float(0)
            }
            timeline_per_dict[formatted_time] = temp_dict
            start_time += time_interval
        
        collection_timeline_emotion_per.insert_one(timeline_per_dict)
        timeline_per_document = collection_timeline_emotion_per.find_one(timeline_per_filter_query)

    # timeline_most_document가 존재하지 않는 경우
    if not timeline_most_document :
        timeline_most_dict = {
            'youtube_index' : youtube_index,
            'timeline_emotion_most_activate' : 7
        }

        # 시작 시간
        start_time = timedelta(seconds=1)

        # 종료 시간
        end_time = timedelta(hours=youtube_length_hour, minutes=youtube_length_minute, seconds=youtube_length_second)

        # 시간 
        time_interval = timedelta(seconds=1)

        # youtube_running_time에 해당하는 이름의 키를 딕셔너리에 생성 벨류는 None으로 저장
        while start_time <= end_time:
            formatted_time = str(start_time)[0:10] #시간데이터 문자열 변환 00:00:00과같은 형식
            timeline_most_dict[formatted_time] = 'None'
            start_time += time_interval
        
        collection_timeline_emotion_most.insert_one(timeline_most_dict)
        timeline_most_document = collection_timeline_emotion_most.find_one(timeline_most_filter_query)

    # watching_data_index 검색을 위한 watching_data_documents 검색
    watching_data_filter_query = {'youtube_index' : youtube_index, 'watching_data_activate' : 7}
    watching_data_documents = collection_youtube_watching_data.find(watching_data_filter_query)

    #빈데이터 생성
    # timeline_num을 갱신할 dict
    timeline_num_dict = {}

    # timeline_per을 갱신할 dict
    timeline_per_dict = {}

    # timeline_most를 갱신할 dict
    timeline_most_dict = {}

     # 시작 시간
    start_time = timedelta(seconds=1)

    # 종료 시간
    end_time = timedelta(hours=youtube_length_hour, minutes=youtube_length_minute, seconds=youtube_length_second)

    # 시간 간격
    time_interval = timedelta(seconds=1)

    while start_time <= end_time:
        formatted_time = str(start_time)[0:10] #시간데이터 문자열 변환 00:00:00과같은 형식
        temp_dict = {
            'happy' : 0,
            'surprise' : 0,
            'angry' : 0,
            'sad' : 0,
            'neutral' :0
        }
        timeline_num_dict[formatted_time] = temp_dict
        temp_dict = {
            'happy' : float(0),
            'surprise' : float(0),
            'angry' : float(0),
            'sad' : float(0),
            'neutral' :float(0)
        }
        timeline_per_dict[formatted_time] = temp_dict
        timeline_most_dict[formatted_time] = 'None'
        start_time += time_interval

    # watching_data_index만 뽑아서 저장
    watching_data_index_list = []
    for watching_data_document in watching_data_documents :
        watching_data_index_list.append(watching_data_document['watching_data_index'])
    #print(watching_data_index_list)

    # watching_data_index를 하나씩 살펴보면서 timeline_emotion_num을 살펴봄
    for watching_data_index in watching_data_index_list :

        #해당 youtube의 watching_data_timeline을 하나씩 살펴본다.
        watching_timeline_filter_query = {'watching_data_index' : watching_data_index, 'watching_timeline_activate' : 7}
        watching_timeline_document = collection_youtube_watching_timeline.find_one(watching_timeline_filter_query)
        #print(watching_timeline_document)

        # 시작 시간
        start_time = timedelta(seconds=1)

        # 종료 시간
        end_time = timedelta(hours=youtube_length_hour, minutes=youtube_length_minute, seconds=youtube_length_second)

        # 시간 간격
        time_interval = timedelta(seconds=1)

        while start_time <= end_time:
            formatted_time = str(start_time)[0:10] #시간데이터 문자열 변환 00:00:00과같은 형식
            emotion = watching_timeline_document[formatted_time] # emotion = 해당 시간의 감정

            # watching_data를 기반으로 감정 개수 갱신
            if emotion == 'happy' :
                timeline_num_dict[formatted_time]['happy'] += 1
            elif emotion == 'surprise' :
                timeline_num_dict[formatted_time]['surprise'] += 1
            elif emotion == 'sad' :
                timeline_num_dict[formatted_time]['sad'] += 1
            elif emotion == 'angry' :
                timeline_num_dict[formatted_time]['angry'] += 1
            elif emotion == 'neutral' :
                timeline_num_dict[formatted_time]['neutral'] += 1

            start_time += time_interval

        # 시작 시간
        start_time = timedelta(seconds=1)

        # 종료 시간
        end_time = timedelta(hours=youtube_length_hour, minutes=youtube_length_minute, seconds=youtube_length_second)

        # 시간 간격
        time_interval = timedelta(seconds=1)
        while start_time <= end_time:
            formatted_time = str(start_time)[0:10] #시간데이터 문자열 변환 00:00:00과같은 형식
            happy_num = timeline_num_dict[formatted_time]['happy']
            surprise_num = timeline_num_dict[formatted_time]['surprise']
            sad_num = timeline_num_dict[formatted_time]['sad']
            angry_num = timeline_num_dict[formatted_time]['angry']
            neutral_num = timeline_num_dict[formatted_time]['neutral']

            emotion_sum = happy_num + surprise_num + sad_num + angry_num + neutral_num

            if happy_num != 0 :
                happy_per = round(happy_num / emotion_sum , 3)
            else :
                happy_per = float(0)
            if neutral_num != 0 :
                neutral_per = round(neutral_num / emotion_sum , 3)
            else :
                neutral_per = float(0)
            if surprise_num != 0 :
                surprise_per = round(surprise_num / emotion_sum , 3)
            else :
                surprise_per = float(0)
            if sad_num != 0 :
                sad_per = round(sad_num / emotion_sum , 3)
            else :
                sad_per = float(0)
            if angry_num != 0 :
                angry_per = round(angry_num / emotion_sum , 3)
            else :
                angry_per = float(0)
            
            timeline_per_dict[formatted_time]['happy'] = happy_per
            timeline_per_dict[formatted_time]['surprise'] = surprise_per
            timeline_per_dict[formatted_time]['angry'] = angry_per
            timeline_per_dict[formatted_time]['sad'] = sad_per
            timeline_per_dict[formatted_time]['neutral'] = neutral_per
            
            emotion_dict = {
                'happy' : happy_num,
                'surprise' : surprise_num,
                'sad' : sad_num,
                'angry' : angry_num,
                'neutral' : neutral_num
            }
            most_emotion = max(emotion_dict, key=emotion_dict.get)
            if happy_num == 0 and surprise_num == 0 and sad_num == 0 and angry_num == 0 and neutral_num == 0 : 
                timeline_most_dict[formatted_time] = 'None'
            else :
                timeline_most_dict[formatted_time] = most_emotion

            start_time += time_interval

    #timeline_num_dict에 저장한 딕셔너리 내용 update
    timeline_num_filter_query = {'youtube_index' : youtube_index, 'timeline_emotion_num_activate' : 7}
    timeline_num_update_query = {'$set' : timeline_num_dict}
    collection_timeline_emotion_num.update_one(timeline_num_filter_query, timeline_num_update_query)

    #timeline_per_dict에 저장한 딕셔너리 내용 update
    timeline_per_filter_query = {'youtube_index' : youtube_index, 'timeline_emotion_per_activate' : 7}
    timeline_per_update_query = {'$set' : timeline_per_dict}
    collection_timeline_emotion_per.update_one(timeline_per_filter_query, timeline_per_update_query)

    #timeline_most_dict에 저장한 딕셔너리 내용 update
    timeline_most_filter_query = {'youtube_index' : youtube_index, 'timeline_emotion_most_activate' : 7}
    timeline_most_update_query = {'$set' : timeline_most_dict}
    collection_timeline_emotion_most.update_one(timeline_most_filter_query, timeline_most_update_query)


    #갱신한 데이터를 바탕으로 youtube_distributon 테이블 데이터 갱신
    #갱신 시에 필요한 도큐먼트가 존재하지 않는다면 생성
    distribution_update(socket_id, watching_data_index)



def distribution_update(socket_id, watching_data_index):
    print('distribution_update진입')
    #먼저 youtube_watching_timeline 테이블에 도큐먼트 생성하기 위해 필요한 데이터 불러오기
    watching_data_filter_query = {'watching_data_index' : watching_data_index, 'watching_data_activate' : 7}
    watching_data_document = collection_youtube_watching_data.find_one(watching_data_filter_query) # watching_data도큐먼트에서 youtube_index와 user_index 불러오기
    youtube_index = watching_data_document['youtube_index']

    #distribution_document가 있는지 검색
    distribution_filter_query = {'youtube_index' : youtube_index, 'distribution_activate' : 7}
    distribution_document = collection_video_distribution.find_one(distribution_filter_query)

    distribution_dict = {}

    watching_data_count = collection_youtube_watching_data.count_documents({'youtube_index' : youtube_index, 'watching_data_activate' : 7})

    emotion_statistics_sum_dict = {
        'neutral' : 0,
        'happy' : 0,
        'surprise' : 0,
        'sad' : 0,
        'angry' : 0
    }

    watching_achivement_per_sum = 0

    #watching_data_num을 찾기 위한 document검색
    youtube_watching_data_filter_query = {'youtube_index' : youtube_index, 'watching_data_activate' : 7}
    youtube_watching_data_documents = collection_youtube_watching_data.find(youtube_watching_data_filter_query)

    # watching_data하나씩 검색
    for youtube_watching_data_document in youtube_watching_data_documents :

        watching_achivement_per_sum += youtube_watching_data_document['watching_achivement_per']

        # 각 감정의 percentage 데이터 불러오기
        neutral_per = youtube_watching_data_document['emotion_statistics_per']['neutral']
        happy_per = youtube_watching_data_document['emotion_statistics_per']['happy']
        surprise_per = youtube_watching_data_document['emotion_statistics_per']['surprise']
        sad_per = youtube_watching_data_document['emotion_statistics_per']['sad']
        angry_per = youtube_watching_data_document['emotion_statistics_per']['angry']

        # 각 감정의 percentage수치 데이터 합산
        emotion_statistics_sum_dict['neutral'] += neutral_per
        emotion_statistics_sum_dict['happy'] += happy_per
        emotion_statistics_sum_dict['surprise'] += surprise_per
        emotion_statistics_sum_dict['sad'] += sad_per
        emotion_statistics_sum_dict['angry'] += angry_per

    # 데이터 개수 갱신
    distribution_dict['watching_data_num'] = watching_data_count

    #watching_achivement_per 갱신
    wathcing_achivement_per = round(watching_achivement_per_sum / watching_data_count , 3)
    distribution_dict['video_achivement_avg'] = wathcing_achivement_per
        
    # 가져온 percentage값들의 총합에서 평균계산
    if emotion_statistics_sum_dict['neutral'] == 0 :
        neutral_avg = float(0)
    else :
        neutral_avg = round(emotion_statistics_sum_dict['neutral'] / watching_data_count , 3)
    if emotion_statistics_sum_dict['happy'] == 0 :
        happy_avg = float(0)
    else :
        happy_avg = round(emotion_statistics_sum_dict['happy'] / watching_data_count , 3)
    if emotion_statistics_sum_dict['surprise'] == 0 :
        surprise_avg = float(0)
    else :
        surprise_avg = round(emotion_statistics_sum_dict['surprise'] / watching_data_count , 3)
    if emotion_statistics_sum_dict['sad'] == 0 :
        sad_avg = float(0)
    else :
        sad_avg = round(emotion_statistics_sum_dict['sad'] / watching_data_count , 3)
    if emotion_statistics_sum_dict['angry'] == 0:
        angry_avg = float(0)
    else :
        angry_avg = round(emotion_statistics_sum_dict['angry'] / watching_data_count , 3)

    distribution_dict['emotion_statistics_avg'] = {
        'neutral' : neutral_avg,
        'happy' : happy_avg,
        'surprise' : surprise_avg,
        'sad' : sad_avg,
        'angry' : angry_avg
    }

    #emotion_statistics_score 갱신
    emotion_statistics_score_dict = {
            'neutral' : round(neutral_avg * 2, 3),
            'happy' : round(happy_avg * 3, 3),
            'surprise' : round(surprise_avg * 4, 3),
            'sad' : round(sad_avg * 3, 3),
            'angry' : round(angry_avg * 3, 3)
    }
    distribution_dict['emotion_statistics_score'] = emotion_statistics_score_dict
    most_emotion = max(emotion_statistics_score_dict, key=emotion_statistics_score_dict.get) # 점수토대로 최다 감정 산출
    distribution_dict['most_emotion'] = most_emotion # 최다 감정

    #print(distribution_dict)

    #distribution_update
    distribution_filter_query = {'youtube_index' : youtube_index, 'distribution_activate' : 7}
    distribution_update_query = {'$set' : distribution_dict}
    collection_video_distribution.update_one(distribution_filter_query, distribution_update_query)

#--------------------------------------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------------------------------------
@socketio.on('disconnect')
def user_socket_disconnect():
    #print('socket is disconnected, saving is start')

    socket_id = request.sid
    index_dict = UserFrameData.get_user_youtube_index(socket_id)

    #UserFrameData.print_list_data(socket_id)

    # 콜렉션 내의 도큐먼트 수 확인
    user_index = index_dict['user_index']
    youtube_index = index_dict['youtube_index']

    print(socket_id)
    print(user_index)
    print(youtube_index)

    user_filter_query = {'user_index' : user_index, 'user_activate' : 7}
    user_document = collection_user.find(user_filter_query)
    if user_document is None :
        return ""

    watching_data_document = collection_youtube_watching_data.find().sort('watching_data_index', -1).limit(1) # watching_data_index를 내림차순으로 정렬
    watching_data_max_index = int(watching_data_document[0]['watching_data_index']) # user_seq 값만 저장
    watching_data_index = watching_data_max_index + 1

    #document_count = collection_youtube_watching_data.count_documents({})
    #index_max_value = document_count + 1
    #watching_data_index = index_max_value
    

    initial_watching_data = {
            'watching_data_index' : watching_data_index,
            'youtube_index' : youtube_index,
            'user_index' : user_index,
            'data_create_time' : datetime.utcnow(),
            'watching_data_activate' : 7,
            'watching_achivement_per' : 'None',
            'emotion_statistics_per' : {
                'neutral' : 'None',
                'happy' : 'None',
                'surprise' : 'None',
                'sad' : 'None',
                'angry' : 'None'
            },
            'emotion_statistics_score' :{
                'neutral' : 'None',
                'happy' : 'None',
                'surprise' : 'None',
                'sad' : 'None',
                'angry' : 'None'
            },
            'most_emotion' : 'None'
        }

    collection_youtube_watching_data.insert_one(initial_watching_data) #데이터베이스에 도큐먼트 삽입

    #youtube_watching_timeline 테이블에 도큐먼트 생성 및 데이터 저장 , 저장한 데이터를 바탕으로 youtube_watching_data 데이터 업데이트
    update_watching_data_table(socket_id, watching_data_index)


if __name__ == '__main__':
   ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS)
   ssl_context.load_cert_chain(certfile='certificate.crt', keyfile='private.key')
   socketio.run(app, debug=True, host="0.0.0.0", port = 443, allow_unsafe_werkzeug=True, ssl_context=ssl_context)