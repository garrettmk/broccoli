FROM python:latest
WORKDIR /broccoli
ADD . /broccoli
RUN apt-get update && apt-get install -y supervisor
RUN pip install -r requirements.txt
EXPOSE 80
ENV FLASK_APP=web.py PYTHONUNBUFFERED=0
RUN useradd -m workeruser
USER workeruser
CMD supervisord -c supervisord.conf