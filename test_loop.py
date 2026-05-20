import requests

session = requests.Session()
response = session.get('http://127.0.0.1:8000/admin/')

print("Initial GET /admin/")
print("History:", response.history)
print("Final URL:", response.url)

# Now login
csrf_token = response.cookies['csrftoken']
login_data = {'username': 'admin@test.com', 'password': 'password', 'csrfmiddlewaretoken': csrf_token, 'next': '/admin/'}
headers = {'Referer': response.url}
response2 = session.post(response.url, data=login_data, headers=headers)

print("After POST login:")
print("History:", response2.history)
print("Final URL:", response2.url)
print("Content length:", len(response2.content))
