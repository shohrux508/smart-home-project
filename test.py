
import requests

data = {
    "devices": [
        {"id": "lamp-1"}
    ]
}

response = requests.post(url='https://shohruxyigitaliev.uz/v1.0/user/devices/query',
                         headers={'Authorization': 'Bearer alice-demo'}, json=data)
response2 = requests.post(url='https://shohruxyigitaliev.uz/v1.0/user/devices',
                          headers={'Authorization': 'Bearer alice-demo'})

print(response.json())
