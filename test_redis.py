import redis
try:
    r = redis.Redis(host='localhost', port=6379, db=0)
    print(r.ping())
except Exception as e:
    print("Redis error:", str(e))
