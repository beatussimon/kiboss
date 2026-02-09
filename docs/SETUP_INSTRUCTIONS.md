# KIBOSS Local Setup Instructions

This document provides step-by-step instructions for setting up KIBOSS locally.

---

## Prerequisites

- Python 3.12+
- pip
- Git
- Docker & Docker Compose (for Redis)

---

## 1. Clone and Setup Virtual Environment

```bash
# Navigate to project directory
cd //wsl.localhost/Ubuntu/home/bea/kiboss

# Create virtual environment
python -m venv kibossvenv

# Activate virtual environment
# On Windows:
kibossvenv\Scripts\activate
# On Linux/Mac:
source kibossvenv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## 2. Start Redis with Docker

```bash
# Start Redis container
docker run -d \
    --name kiboss-redis \
    -p 6379:6379 \
    redis:7-alpine

# Verify Redis is running
docker ps

# Test Redis connection
redis-cli ping
```

---

## 3. Configure Environment

Create a `.env` file in the project root:

```env
# Django settings
DEBUG=True
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=*

# Database (SQLite by default)
DATABASE_URL=sqlite:///db.sqlite3

# Redis
REDIS_URL=redis://localhost:6379/0

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# JWT
ACCESS_TOKEN_LIFETIME_MINUTES=15
REFRESH_TOKEN_LIFETIME_DAYS=7
```

---

## 4. Run Migrations

```bash
# Create database tables
python manage.py migrate

# Verify migrations
python manage.py showmigrations
```

---

## 5. Create Superuser

```bash
# Create admin user
python manage.py createsuperuser

# Follow prompts for email, password, etc.
```

---

## 6. Start Development Server

```bash
# Run Django development server
python manage.py runserver 0.0.0.0:8000

# Server will be available at http://localhost:8000
```

---

## 7. Start Celery Worker (Background Tasks)

Open a new terminal:

```bash
# Activate virtual environment
cd //wsl.localhost/Ubuntu/home/bea/kiboss
source kibossvenv/bin/activate

# Start Celery worker
celery -A kiboss worker -l info

# Optional: Start Celery beat for scheduled tasks
celery -A kiboss beat -l info
```

---

## 8. Verify Installation

### Access Points:

| Service | URL |
|---------|-----|
| Django Admin | http://localhost:8000/admin/ |
| API Schema | http://localhost:8000/api/schema/ |
| Swagger UI | http://localhost:8000/api/docs/ |
| ReDoc | http://localhost:8000/api/redoc/ |

### Test API Authentication:

```bash
# Get JWT token
curl -X POST http://localhost:8000/api/auth/token/ \
    -H "Content-Type: application/json" \
    -d '{"email": "admin@example.com", "password": "your-password"}'

# Access protected endpoint
curl http://localhost:8000/api/bookings/ \
    -H "Authorization: Bearer <your-access-token>"
```

---

## 9. Docker Compose (Alternative)

For a complete environment with Redis:

```yaml
# docker-compose.yml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    
  web:
    build: .
    command: python manage.py runserver 0.0.0.0:8000
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
    
  celery:
    build: .
    command: celery -A kiboss worker -l info
    volumes:
      - .:/app
    environment:
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
```

Start with:
```bash
docker-compose up -d
```

---

## 10. Testing

### Run Unit Tests:

```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test kiboss.apps.bookings

# Run with coverage
pip install coverage
coverage run --source='kiboss' manage.py test
coverage report
```

---

## 11. Troubleshooting

### Redis Connection Error

```bash
# Check if Redis is running
docker ps

# Restart Redis container
docker restart kiboss-redis

# Test connection
redis-cli ping
```

### Migration Issues

```bash
# Check for pending migrations
python manage.py showmigrations

# Reset database (development only!)
rm db.sqlite3
python manage.py migrate
```

### Port Already in Use

```bash
# Find process using port 8000
lsof -i :8000

# Kill the process
kill <pid>
```

---

## 12. Development Commands

```bash
# Generate new migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Create app
python manage.py startapp new_app

# Check for issues
python manage.py check

# Collect static files
python manage.py collectstatic
```

---

## 13. API Endpoints Summary

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/token/` | POST | Get JWT tokens |
| `/api/auth/token/refresh/` | POST | Refresh access token |
| `/api/bookings/` | GET/POST | List/Create bookings |
| `/api/bookings/{id}/` | GET | Get booking details |
| `/api/bookings/{id}/cancel/` | POST | Cancel booking |
| `/api/bookings/{id}/start/` | POST | Start booking |
| `/api/bookings/{id}/complete/` | POST | Complete booking |
| `/api/assets/` | GET/POST | List/Create assets |
| `/api/payments/` | GET | List payments |

---

## 14. Next Steps

1. Review the API documentation at `/api/docs/`
2. Create test data using Django Admin
3. Run integration tests
4. Configure production settings for deployment

---

For more details, see the complete documentation in the `docs/` directory.
