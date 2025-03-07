FROM python:3.12-slim
WORKDIR /app
ADD requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
ADD . .
ENTRYPOINT ["python", "main.py"]