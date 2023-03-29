from django.shortcuts import render
import os
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view
from _thread import *
from dotenv import load_dotenv
import openai
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import json
from django.http import JsonResponse
import pyrebase

load_dotenv()

DB_USER = "User"
DB_CHAT = "Chat"
DB_EMOTION = "Emotion"
DB_IMAGE = "Image"
DB_SUMMARY = "Summary"
STORAGE_EMOTIONCHAT = "emotionChat"


config = {
  "type": os.getenv("CONFIG_TYPE"),
  "project_id": os.getenv("CONFIG_PROJECT_ID"),
  "apiKey": os.getenv("CONFIG_APIKEY"),
  "private_key_id": os.getenv("CONFIG_PRIVATE_KEY_ID"),
  "private_key": os.getenv("CONFIG_PRIVATE_KEY"),
  "client_email": os.getenv("CONFIG_CLIENT_EMAIL"),
  "client_id": os.getenv("CONFIG_CLIENT_ID"),
  "auth_uri": os.getenv("CONFIG_AUTH_URI"),
  "token_uri": os.getenv("CONFIG_TOKEN_URI"),
  "auth_provider_x509_cert_url": os.getenv("CONFIG_AUTH_PROVIDER_X509_CERT_URL"),
  "client_x509_cert_url": os.getenv("CONFIG_CLIENT_X509_CERT_URL")
}

firebaseConfig = {
  "apiKey": os.getenv("CONFIG_APIKEY"),
  "authDomain": os.getenv("CONFIG_AUTH_DOMAIN"),
  "databaseURL": os.getenv("CONFIG_DATABASE_URL"),
  "projectId": os.getenv("CONFIG_PROJECT_ID"),
  "storageBucket": os.getenv("CONFIG_STORAGE_BUCKET"),
  "messagingSenderId": os.getenv("CONFIG_MESSAGING_SENDER_ID"),
  "appId": os.getenv("CONFIG_APP_ID"),
  "measurementId": os.getenv("CONFIG_MEASUREMENT_ID")
}


cred = credentials.Certificate("alda-2fa29-firebase-adminsdk-moumd-2044dd4774.json")  # prod db
# cred = credentials.Certificate("alda-f895d-716aacfba849.json")  # dev db 1(by firebase package)
app = firebase_admin.initialize_app(cred)
db = firestore.client()
db_user = db.collection(DB_USER)



# firebase storage
firebase = pyrebase.initialize_app(firebaseConfig) # dev db 2(by pyrebase package)
storage = firebase.storage()
auth = firebase.auth()
email = os.getenv("PYREBASE_EMAIL")
password = os.getenv("PYREBASE_PASSWORD")
user = auth.sign_in_with_email_and_password(email, password)


# openai API
openai.api_key = os.getenv("OPENAI_API_KEY")

model_engine = "gpt-3.5-turbo"
max_tokens = 100
temperature = 0.7
top_p = 0.7


def save_url(user_id, image):
    created_at = datetime.today().strftime("%Y%m%d")
    storage.child(f"{STORAGE_EMOTIONCHAT}/{user_id}/{created_at}").put(image)
    token = pyrebase_login(email, password)
    return storage.child(f"{STORAGE_EMOTIONCHAT}/{user_id}/{created_at}").get_url(token)



def put_firebase(user_id):
    pass


def pyrebase_login(email, password):
    user = auth.sign_in_with_email_and_password(email, password)
    return user["idToken"]




# 세부감정 여러 개 보낼 때 데이터 처리
def multiple_feelings(ufs):
    result = ufs[0]
    if len(ufs) == 1:
        return result
    for u in ufs[1:]:
        result += f", {u}"
    return result


def initialize_message(first_name, last_name, userfeeling_big, userfeeling_small, language=None):

    mufs = multiple_feelings(userfeeling_small)

    baseline_prompt_eng = [{"role": "system", "content": f"""
        Information: You are a psychological counselor. Your patient is experiencing dementia. 
        Your patient's name is '{first_name} {last_name}', and please refer to him or her as {first_name}, not grandfather or grandmother. 
        Please speak politely when talking. Please begin the counseling based on this information."""},
        {"role": "system", "content": "How was your feelings today?"},
        {"role": "user", "content": f"I felt {mufs} among the {userfeeling_big} feelings."}]

    if language is None or language != "kor":
        return baseline_prompt_eng


    baseline_prompt_kor = [{"role": "system", "content": f"""
        정보 : 당신은 심리상담사입니다. 당신이 상담할 환자는 치매를 겪고 있습니다. 
        환자명은 '{last_name}{first_name}'이며 부를 때에 할아버지, 할머니가 아닌 {last_name}{first_name}님으로 부르세요. 얘기를 할 때는 공손하게 얘기하세요. 
        정보를 바탕으로 상담을 시작하세요."""},
        {"role": "system", "content": "오늘 기분이 어떠셨어요?"},
        {"role": "user", "content": f"오늘은 {userfeeling_big}, {mufs} 등을 느꼈어요."}]

    return baseline_prompt_kor


def initialize_fun(user_name):
    return [{"role": "system", "content": f"You are a psychologist. The patient you are going to consult is suffering from dementia. The patient’s name is {user_name}, and call him or her as {user_name}, not grandfather or grandmother. When you talk, be polite. Start talking about the sentences or words {user_name} is talking about."}]

def convert_string_to_list(string):
    string = string[1:-1]
    string = string.replace(' {','{').replace(' }','}').replace('{ ','{').replace('} ','}').replace('},{','}/{')
    str_list = string.split('/')
    result = []
    for sl in str_list:
        dicts = json.loads(sl)
        result.append(dicts)
    return result


def get_language(lang):
    if lang is None or lang == "eng":
        return "eng"
    return "kor"


@api_view(http_method_names=['POST'])
def chat_emotion(request):

    audio_data = request.FILES.get('audio')
    messages_data = request.data.get('messages')
    user_id = request.data.get('user_id')
    userfeeling_big = request.data.get('userfeeling_big')
    userfeeling_small = request.data.get('userfeeling_small')
    user = None
    try:
        user = get_user_dict(user_id)
    except UserNotFoundException as unfe:
        return Response(status=status.HTTP_404_NOT_FOUND, data={"error": str(unfe)})
    user_ref = get_user_ref(user_id)

    language = get_language(request.data.get('language'))
    messages = convert_string_to_list(messages_data) if isinstance(messages_data, str) else messages_data

    if not messages:
        # generate initial message and gpt response
        prompt = initialize_message(user["firstName"], user["lastName"], userfeeling_big, userfeeling_small, language)
        response = openai.ChatCompletion.create(model = "gpt-3.5-turbo", messages=prompt)
        system_message = response["choices"][0]["message"]["content"]
        return Response(status=status.HTTP_200_OK, data=[{"role": "system", "content": system_message}])
    
    else:
        prompt = initialize_message(user["firstName"], user["lastName"], userfeeling_big, userfeeling_small, language)
       
        audio = audio_data.open()
        # audio_file = open(audio, "rb")
        audio_file = audio
        transcript = openai.Audio.transcribe("whisper-1", audio_file)

        # messages.insert(0, prompt)
        prompt.extend(messages)
        prompt.append({"role": "user", "content": transcript["text"]})

        response = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=prompt)
        system_message = response["choices"][0]["message"]["content"]
        return Response(status=status.HTTP_200_OK, data=[{"role": "user", "content": transcript["text"]},{"role": "system", "content": system_message}])


@api_view(http_method_names=['POST'])
def chat_fun(request):
    audio_data = request.FILES.get('audio')
    messages_data = request.data.get('messages')
    user_id = request.data.get('user_id')
    user = None

    try:
        user = get_user_dict(user_id)
    except UserNotFoundException as unfe:
        return Response(status=status.HTTP_404_NOT_FOUND, data={"error": str(unfe)})
    user = get_user_dict(user_id)

    audio = audio_data.open()
    transcript = openai.Audio.transcribe("whisper-1", audio)
    prompt = initialize_fun(user["firstName"])

    if not messages_data:
        prompt.append({"role": "user", "content": transcript["text"]})
        response = openai.ChatCompletion.create(model = "gpt-3.5-turbo", messages=prompt)
        system_message = response["choices"][0]["message"]["content"]
        return Response(status=status.HTTP_200_OK, data=[{"role": "user", "content": transcript["text"]}, {"role": "system", "content": system_message}])
    
    else:
        messages = convert_string_to_list(messages_data) if isinstance(messages_data, str) else messages_data
        prompt.extend(messages)
        prompt.append({"role": "user", "content": transcript["text"]})
        response = openai.ChatCompletion.create(model = "gpt-3.5-turbo", messages=prompt)
        system_message = response["choices"][0]["message"]["content"]
        return Response(status=status.HTTP_200_OK, data=[{"role": "user", "content": transcript["text"]},{"role": "system", "content": system_message}])


@api_view(http_method_names=['POST'])
def save_conversation(request):
    messages = request.data.get('messages')
    user_id = request.data.get('user_id')   # or get it from cookie(?)/header(?)
    image = request.FILES.get('image')
    summary = request.data.get('summary')
    chat_type = request.data.get('chat_type')
    userfeeling_big = request.data.get('userfeeling_big')
    userfeeling_small = request.data.get('userfeeling_small')
    chat_type = chat_type if chat_type is not None else "emotion"

    user = get_user_dict(user_id)
    user_ref = get_user_ref(user_id)

    # 1. chat 데이터 저장
    # prev logic
    chat_data = {"user": user_ref, "createdAt": firestore.SERVER_TIMESTAMP, "messages": messages, "summary": summary, "type": chat_type}
    update_time, chat_ref = db.collection(DB_CHAT).add(chat_data)

    # 2. emotion 데이터 저장
    emotion_data = {"createdAt": firestore.SERVER_TIMESTAMP, "user": user_ref, "big": userfeeling_big, "small": userfeeling_small, "chat": chat_ref}
    update_time, emotion_ref = db.collection(DB_EMOTION).add(emotion_data)
    
    # 3. 이미지 저장 by cloud storage
    image_url = save_url(user_id, image)
    image_data = {"createdAt": firestore.SERVER_TIMESTAMP, "user": user_ref, "emotion": emotion_ref, "image": image_url, "chat": chat_ref}
    update_time, image_ref = db.collection(DB_IMAGE).add(image_data)
    return Response(status=status.HTTP_201_CREATED, data={"chatId": chat_ref.id, "emotionId": emotion_ref.id, "imageId": image_ref.id})


@api_view(http_method_names=['GET'])
def home(request):
    return Response(status=status.HTTP_200_OK, data={"msg": "welcome to alda"})


def get_user_dict(user_id):
    info = db_user.document(user_id).get().to_dict()
    if (info is None) is True:
        raise UserNotFoundException(f"id='{user_id}'에 해당하는 유저가 없습니다.")
    return info


def get_user_ref(user_id):
    ref = db_user.document(user_id)
    if ref.get().to_dict() is None:
        raise UserNotFoundException(f"id='{user_id}'에 해당하는 유저가 없습니다.")
    return ref


@api_view(http_method_names=["GET"])
def get_users(request):
    user_id = request.GET.get("userId")
    user_dict = db_user.document(user_id).get().to_dict()
    return JsonResponse(status=status.HTTP_200_OK, data={"user": user_dict})



def summary_by_keyword(input_string, language="eng"):
    prompt = None
    if language == "kor":
        prompt = [{"role": "system", "content": "정보: 다음의 대화를 3개의 단어로 요약해줘."}]
    else:
        prompt = [{"role": "system", "content": "Information: Please summarize the following conversation in 3 keywords."}]
    prompt.append({"role": "user", "content": input_string})
    response = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=prompt)
    keyword = response["choices"][0]["message"]["content"]
    keyword = keyword.replace(".", "").replace(" ", "").lower().split(',')
    return keyword


def summary_and_drawing(input_sequence, language="eng"):

    prompt = None
    if language == "kor":
        prompt = [{"role": "system", "content": "정보: 다음의 대화를 영어로 요약해줘."}]
    else:
        prompt = [{"role": "system", "content": "Information: Please summarize the following conversation in English."}]
    conversation, user_conversation = "", ""
    uconv_count = 0

    for i in input_sequence:
        pline = i["role"] + ": " + i["content"] + "\n"
        conversation += pline
        if i["role"] == "user":
            user_conversation += pline
            uconv_count += 1

    prompt.append({"role": "user", "content": conversation})
    response = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=prompt)

    image_prompt = "Give me a painting following the conversation." + response["choices"][0]["message"]["content"]
    
    image_response = openai.Image.create(
        prompt=image_prompt,
        n=3,
        size="1024x1024"
    )

    # user conversation 일정 기준 이상일 때만 user 대화만으로 키워드 리턴
    if uconv_count >= 2:
        return image_response['data'][0]['url'], user_conversation
    else:
        return image_response['data'][0]['url'], conversation


@api_view(http_method_names=["POST"])
def download_image(request):
    image_id = request.data.get("image")
    image_url = db.collection(DB_IMAGE).document(image_id).get().to_dict()["image"]
    return Response(status=status.HTTP_200_OK, data={"image": image_url})



@api_view(http_method_names=["POST"])
def image_generate(request):
    image_url, message_string = None, None
    language = request.data.get("language")
    messages = request.data.get("messages")
    user_id = request.data.get("user_id")
    user_ref = get_user_ref(user_id)
    
    # emotion_ref = db.collection(DB_EMOTION).where("user", "==", user_ref).order_by("createdAt", direction=firestore.Query.DESCENDING).limit(1).get()[0].reference
    
    if language is None or language == "eng":
        image_url, message_string = summary_and_drawing(messages)
    else:
        image_url, message_string = summary_and_drawing(messages, "kor")

    # summarize by keywords(up to 3)
    keywords = summary_by_keyword(message_string)
    return Response(status=status.HTTP_200_OK, data={"image": image_url, "keywords": keywords})



class UserNotFoundException(BaseException):
    pass



