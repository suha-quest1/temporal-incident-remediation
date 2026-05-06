FROM python:3.11

WORKDIR /app

COPY api/requirements.txt api/requirements.txt
RUN pip install -r api/requirements.txt

COPY . .

ENV PYTHONPATH=/app

CMD ["python", "-m", "api.server"]