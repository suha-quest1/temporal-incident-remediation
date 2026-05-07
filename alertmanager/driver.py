import time
import requests


time.sleep(15)

payload = {}

response = requests.post(
    "http://api-server:8000/incidents/start",
    json=payload,
)

print(response.text)