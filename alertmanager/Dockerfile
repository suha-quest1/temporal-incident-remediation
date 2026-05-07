FROM python:3.11

WORKDIR /app

RUN pip install requests

COPY alertmanager/driver.py .

CMD ["python", "driver.py"]