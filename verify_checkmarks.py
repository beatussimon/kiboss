import os
import django
import redis
import base64
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kiboss.settings')
django.setup()

from kiboss.apps.users.serializers import PublicUserSerializer
from django.contrib.auth import get_user_model

User = get_user_model()

# Check Redis
try:
    r = redis.Redis(host='localhost', port=6379, db=0)
    plus_data = r.get('asset:checkmark:premium')
    business_data = r.get('asset:checkmark:business')

    print(f"Plus data in Redis: {plus_data.decode('utf-8')[:50] if plus_data else 'None'}...")
    print(f"Business data in Redis: {business_data.decode('utf-8')[:50] if business_data else 'None'}...")
except Exception as e:
    print(f"Redis error: {e}")

# Check Serializer
user = User.objects.filter(is_identity_verified=True).first()
if user:
    serializer = PublicUserSerializer(user)
    data = serializer.data
    print(f"User {user.email} (Verified) checkmark_data: {data.get('checkmark_data')[:50] if data.get('checkmark_data') else 'None'}...")
else:
    print("No verified user found for test.")

user_biz = User.objects.filter(corporate_profile__verification_status='VERIFIED').first()
if user_biz:
    serializer = PublicUserSerializer(user_biz)
    data = serializer.data
    print(f"User {user_biz.email} (Business) checkmark_data: {data.get('checkmark_data')[:50] if data.get('checkmark_data') else 'None'}...")
else:
    print("No business user found for test.")
