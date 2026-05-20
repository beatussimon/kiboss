import requests
import time

session = requests.Session()
response = session.get('http://127.0.0.1:8000/admin/login/?next=/admin/')
csrf_token = response.cookies['csrftoken']
login_data = {'username': 'admin@test.com', 'password': 'password', 'csrfmiddlewaretoken': csrf_token, 'next': '/admin/'}
headers = {'Referer': 'http://127.0.0.1:8000/admin/login/?next=/admin/'}

t0 = time.time()
response = session.post('http://127.0.0.1:8000/admin/login/?next=/admin/', data=login_data, headers=headers)
t1 = time.time()

print("Login took:", t1 - t0, "seconds")
print("Status code:", response.status_code)
print("URL:", response.url)
