FROM python:latest
WORKDIR /broccoli
ADD . /broccoli
RUN pip install -r requirements.txt
EXPOSE 80
#ENTRYPOINT ["python", "celery.py"]
CMD ["python", "celery.py"]