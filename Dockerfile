# PREVIOUS VERSION(error due to start.sh -> No file or such directory)

# #아래 적힌 이미지를 베이스 이미지로 한다.
# #이 명령어가 실행되면 Dockerhub에서 해당 이미지를 pull한다.
# FROM python:3.10

# #mkdir 명령어를 실행한다.
# RUN mkdir /code

# #동작 디렉토리를 /code로 옮긴다.
# WORKDIR /code

# # torch package cache memory에 저장 안되는 오류 방지
# RUN pip install torch --no-cache-dir
# RUN pip install nvidia-cudnn-cu11==8.5.0.96 --no-cache-dir

# #requirement.txt를 code 아래로 옮긴다.
# ADD ./requirements.txt /code/requirements.txt 

# #requirement.txt를 읽어서 필요한 패키지를 다운받는다
# RUN pip install -r /code/requirements.txt 
# # RUN pip install -r requirements.txt
# #python과 nginx를 연결해주는 interface
# RUN pip install gunicorn 

# #현재 디렉토리를 /code에 복사해서 넣겠다
# # ADD . /code 
# # bash script 권한 설정
# RUN ["chmod", "+x", "start.sh"] 
# # bash script 실행, 이 스크립트는 다음 챕터에서 만들겠다
# ENTRYPOINT ["sh","./start.sh"] 

# NEW VERSION

# ./Dockerfile 
FROM python:3.10
# WORKDIR /usr/src/app

## Install packages
COPY requirements.txt ./
RUN pip install --no-cache-dir torch==1.13.1
RUN pip install --root-user-action=ignore -r requirements.txt

## Copy all src files
COPY . .

## Run the application on the port 8080
EXPOSE 8000

# gunicorn 배포 명령어
# CMD ["gunicorn", "--bind", "허용하는 IP:열어줄 포트", "project.wsgi:application"]
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "alda_project.wsgi:application"]
# CMD ["gunicorn", "pragmatic.wsgi", "--bind", "0.0.0.0:8000"]

