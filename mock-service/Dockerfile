FROM python:3.11

WORKDIR /app

RUN pip install fastapi uvicorn

COPY mock-service/server.py .

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]