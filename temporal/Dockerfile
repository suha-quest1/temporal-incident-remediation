FROM python:3.11

WORKDIR /app

COPY temporal/requirements.txt temporal/requirements.txt
RUN pip install -r temporal/requirements.txt

COPY . .

ENV PYTHONPATH=/app

CMD ["python", "-m", "temporal.worker"]