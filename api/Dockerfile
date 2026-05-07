FROM python:3.11

WORKDIR /app

COPY api/requirements.txt api/requirements.txt
COPY temporal/requirements.txt temporal/requirements.txt

RUN pip install -r api/requirements.txt
RUN pip install -r temporal/requirements.txt

COPY . .

ENV PYTHONPATH=/app

CMD [  "uvicorn",   "api.server:app",  "--host",   "0.0.0.0",   "--port",  "8000"]