# DRF API Endpoints for KIBOSS

This document describes all Django REST Framework API endpoints for KIBOSS.

---

## 1. API Overview

### 1.1 Base URL

```
Local Development: http://localhost:8000/api/v1/
Schema: http://localhost:8000/api/schema/
Swagger UI: http://localhost:8000/api/docs/
```

### 1.2 Authentication

All endpoints require JWT authentication except:
- `/api/v1/auth/register/`
- `/api/v1/auth/login/`
- `/api/v1/auth/refresh/`

```http
Authorization: Bearer <access_token>
```

### 1.3 Rate Limits

- Anonymous: 100 requests/hour
- Authenticated: 1000 requests/hour
- Rate limit headers included in responses

---

## 2. Authentication Endpoints

### 2.1 Register User

```http
POST /api/v1/auth/register/
Content-Type: application/json

{
    "email": "user@example.com",
    "password": "securepassword123",
    "password_confirm": "securepassword123",
    "first_name": "John",
    "last_name": "Doe"
}
```

**Response (201 Created):**
```json
{
    "message": "Registration successful. Please verify your email.",
    "user_id": "uuid",
    "email": "user@example.com"
}
```

### 2.2 Login

```http
POST /api/v1/auth/login/
Content-Type: application/json

{
    "email": "user@example.com",
    "password": "securepassword123"
}
```

**Response (200 OK):**
```json
{
    "access": "eyJ...",
    "refresh": "eyJ...",
    "access_expires": 900,
    "refresh_expires": 604800,
    "user": {
        "id": "uuid",
        "email": "user@example.com",
        "is_verified": false
    }
}
```

### 2.3 Refresh Token

```http
POST /api/v1/auth/refresh/
Content-Type: application/json

{
    "refresh": "eyJ..."
}
```

**Response (200 OK):**
```json
{
    "access": "new_access_token",
    "access_expires": 900
}
```

### 2.4 Logout

```http
POST /api/v1/auth/logout/
Authorization: Bearer <access_token>

{
    "refresh_token": "eyJ..."
}
```

**Response (200 OK):**
```json
{
    "message": "Successfully logged out"
}
```

### 2.5 Change Password

```http
POST /api/v1/auth/password/change/
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "old_password": "currentpassword",
    "new_password": "newsecurepassword123",
    "new_password_confirm": "newsecurepassword123"
}
```

---

## 3. User Endpoints

### 3.1 Current User Profile

```http
GET /api/v1/users/me/
Authorization: Bearer <access_token>
```

**Response (200 OK):**
```json
{
    "id": "uuid",
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "is_email_verified": true,
    "is_phone_verified": false,
    "is_identity_verified": false,
    "trust_score": "75.00",
    "total_ratings_count": 10,
    "is_blocked": false,
    "profile": {
        "phone": "+1234567890",
        "avatar": "/media/avatars/avatar.jpg",
        "bio": "...",
        "city": "New York",
        "country": "USA",
        "timezone": "America/New_York"
    }
}
```

### 3.2 Update Profile

```http
PATCH /api/v1/users/me/
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "first_name": "John",
    "last_name": "Doe",
    "profile": {
        "phone": "+1234567890",
        "bio": "New bio",
        "timezone": "America/New_York"
    }
}
```

### 3.3 User Public Profile

```http
GET /api/v1/users/{user_id}/public/
```

**Response (200 OK):**
```json
{
    "id": "uuid",
    "first_name": "John",
    "last_name": "D.",
    "avatar": "/media/avatars/avatar.jpg",
    "trust_score": "75.00",
    "total_ratings_count": 10,
    "member_since": "2024-01-15T10:30:00Z",
    "is_verified": true,
    "verified_identity": true
}
```

### 3.4 List User Roles

```http
GET /api/v1/users/me/roles/
Authorization: Bearer <access_token>
```

**Response (200 OK):**
```json
{
    "roles": [
        {
            "role": "OWNER",
            "scope_type": "",
            "scope_id": null,
            "expires_at": null
        }
    ]
}
```

---

## 4. Asset Endpoints

### 4.1 List Assets

```http
GET /api/v1/assets/
Authorization: Bearer <access_token>
Query Parameters:
    - asset_type: ROOM | TOOL | VEHICLE | SEAT_SERVICE | TIME_SERVICE
    - city: string
    - country: string
    - min_price: number
    - max_price: number
    - available_from: date
    - available_to: date
    - page: number (default: 1)
    - page_size: number (default: 20, max: 100)
```

**Response (200 OK):**
```json
{
    "count": 150,
    "next": "http://localhost:8000/api/v1/assets/?page=2",
    "previous": null,
    "results": [
        {
            "id": "uuid",
            "name": "Modern Downtown Apartment",
            "asset_type": "ROOM",
            "description": "Beautiful apartment in city center",
            "city": "New York",
            "country": "USA",
            "price_per_unit": "50.00",
            "unit_type": "HOUR",
            "capacity": 4,
            "average_rating": "4.75",
            "total_reviews": 25,
            "is_verified": true,
            "primary_photo": "/media/asset_photos/photo1.jpg",
            "owner": {
                "id": "uuid",
                "first_name": "Jane",
                "avatar": "/media/avatars/jane.jpg",
                "trust_score": "80.00"
            }
        }
    ]
}
```

### 4.2 Create Asset

```http
POST /api/v1/assets/
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "name": "Modern Downtown Apartment",
    "description": "Beautiful apartment in city center",
    "asset_type": "ROOM",
    "address": "123 Main St",
    "city": "New York",
    "state": "NY",
    "country": "USA",
    "postal_code": "10001",
    "latitude": "40.7128",
    "longitude": "-74.0060",
    "jurisdiction": "US-NY",
    "timezone": "America/New_York",
    "properties": {
        "bedrooms": 2,
        "bathrooms": 1,
        "square_feet": 800,
        "amenities": ["wifi", "kitchen", "washer"]
    },
    "pricing_rules": [
        {
            "name": "Standard Rate",
            "unit_type": "HOUR",
            "price": "50.00",
            "min_duration_minutes": 60,
            "priority": 0
        }
    ],
    "availability_rules": [
        {
            "name": "Standard Availability",
            "availability_type": "SCHEDULED",
            "buffer_minutes": 30,
            "min_advance_booking_minutes": 60,
            "max_advance_booking_days": 30,
            "days_of_week": [0, 1, 2, 3, 4, 5, 6],
            "available_from": "08:00",
            "available_to": "22:00"
        }
    ],
    "capacities": [
        {
            "capacity_type": "GUEST",
            "quantity": 4
        }
    ],
    "time_granularity": {
        "min_duration_minutes": 60,
        "max_duration_minutes": 480,
        "increment_minutes": 30,
        "any_start_time": true
    }
}
```

### 4.3 Retrieve Asset

```http
GET /api/v1/assets/{asset_id}/
Authorization: Bearer <access_token>
```

**Response (200 OK):**
```json
{
    "id": "uuid",
    "name": "Modern Downtown Apartment",
    "asset_type": "ROOM",
    "description": "...",
    "address": "123 Main St",
    "city": "New York",
    "country": "USA",
    "is_verified": true,
    "verification_status": "VERIFIED",
    "owner": {
        "id": "uuid",
        "first_name": "Jane",
        "avatar": "...",
        "trust_score": "80.00"
    },
    "pricing_rules": [...],
    "availability_rules": [...],
    "capacities": [...],
    "time_granularity": {...},
    "properties": {...},
    "photos": [...],
    "average_rating": "4.75",
    "total_reviews": 25,
    "total_bookings": 50,
    "created_at": "2024-01-15T10:30:00Z"
}
```

### 4.4 Update Asset

```http
PATCH /api/v1/assets/{asset_id}/
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "name": "Updated Apartment Name",
    "description": "Updated description",
    "is_active": true
}
```

### 4.5 Delete Asset

```http
DELETE /api/v1/assets/{asset_id}/
Authorization: Bearer <access_token>
```

### 4.6 Check Availability

```http
GET /api/v1/assets/{asset_id}/availability/
Authorization: Bearer <access_token>
Query Parameters:
    - start_time: datetime (ISO 8601)
    - end_time: datetime (ISO 8601)
    - quantity: number (default: 1)
```

**Response (200 OK):**
```json
{
    "asset_id": "uuid",
    "requested_start": "2024-02-01T10:00:00Z",
    "requested_end": "2024-02-01T12:00:00Z",
    "is_available": true,
    "available_quantity": 4,
    "price_quote": {
        "base_price": "100.00",
        "service_fee": "10.00",
        "taxes": "8.00",
        "total": "118.00",
        "currency": "USD",
        "breakdown": {...}
    }
}
```

---

## 5. Booking Endpoints

### 5.1 Create Booking

```http
POST /api/v1/bookings/
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "asset_id": "uuid",
    "start_time": "2024-02-01T10:00:00Z",
    "end_time": "2024-02-01T12:00:00Z",
    "quantity": 2,
    "payment_method": "CREDIT_CARD",
    "renter_notes": "Checking in at 10am"
}
```

**Response (201 Created):**
```json
{
    "id": "uuid",
    "status": "PENDING",
    "renter": "uuid",
    "asset": {
        "id": "uuid",
        "name": "Modern Downtown Apartment"
    },
    "start_time": "2024-02-01T10:00:00Z",
    "end_time": "2024-02-01T12:00:00Z",
    "quantity": 2,
    "unit_price": "50.00",
    "subtotal": "100.00",
    "service_fee": "10.00",
    "taxes": "8.00",
    "total_price": "118.00",
    "currency": "USD",
    "payment": {
        "id": "uuid",
        "status": "PENDING",
        "amount": "118.00"
    },
    "contract": {
        "id": "uuid",
        "status": "PENDING"
    },
    "created_at": "2024-01-20T10:30:00Z",
    "expires_at": "2024-01-20T10:45:00Z"
}
```

### 5.2 List Bookings

```http
GET /api/v1/bookings/
Authorization: Bearer <access_token>
Query Parameters:
    - status: PENDING | CONFIRMED | ACTIVE | COMPLETED | CANCELLED | EXPIRED | DISPUTED
    - role: RENTER | OWNER
    - start_time_gte: datetime
    - start_time_lte: datetime
    - page: number
```

**Response (200 OK):**
```json
{
    "count": 25,
    "results": [
        {
            "id": "uuid",
            "status": "CONFIRMED",
            "start_time": "2024-02-01T10:00:00Z",
            "end_time": "2024-02-01T12:00:00Z",
            "asset": {
                "id": "uuid",
                "name": "Modern Downtown Apartment",
                "primary_photo": "..."
            },
            "renter": {...},
            "owner": {...},
            "total_price": "118.00",
            "contract": {
                "status": "EXECUTED"
            }
        }
    ]
}
```

### 5.3 Retrieve Booking

```http
GET /api/v1/bookings/{booking_id}/
Authorization: Bearer <access_token>
```

### 5.4 Confirm Payment

```http
POST /api/v1/bookings/{booking_id}/confirm_payment/
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "payment_intent_id": "pi_...",
    "payment_method_id": "pm_..."
}
```

**Response (200 OK):**
```json
{
    "id": "uuid",
    "status": "CONFIRMED",
    "payment": {
        "id": "uuid",
        "status": "ESCROW",
        "escrow_held_at": "2024-01-20T10:32:00Z"
    },
    "contract": {
        "id": "uuid",
        "status": "ACCEPTED"
    }
}
```

### 5.5 Accept Contract

```http
POST /api/v1/bookings/{booking_id}/accept_contract/
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "signature": {
        "signed_at": "2024-01-20T10:33:00Z",
        "ip_address": "192.168.1.1",
        "user_agent": "Mozilla/5.0..."
    }
}
```

### 5.6 Cancel Booking

```http
POST /api/v1/bookings/{booking_id}/cancel/
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "reason": "Plans changed"
}
```

**Response (200 OK):**
```json
{
    "id": "uuid",
    "status": "CANCELLED",
    "cancellation_reason": "Plans changed",
    "cancellation_fee": "0.00",
    "refund_amount": "118.00",
    "refund_status": "PROCESSING"
}
```

### 5.7 Start Booking

```http
POST /api/v1/bookings/{booking_id}/start/
Authorization: Bearer <access_token>
```

**Response (200 OK):**
```json
{
    "id": "uuid",
    "status": "ACTIVE",
    "started_at": "2024-02-01T10:00:00Z"
}
```

### 5.8 Complete Booking

```http
POST /api/v1/bookings/{booking_id}/complete/
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "actual_return_time": "2024-02-01T12:05:00Z",
    "notes": "Left the place clean",
    "asset_condition": "GOOD"
}
```

### 5.9 Raise Dispute

```http
POST /api/v1/bookings/{booking_id}/dispute/
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "reason": "DAMAGE",
    "description": "The apartment had significant damage when I arrived",
    "disputed_amount": "500.00",
    "evidence": [
        {"type": "IMAGE", "url": "/media/evidence/damage1.jpg"}
    ]
}
```

### 5.10 Booking Timeline

```http
GET /api/v1/bookings/{booking_id}/timeline/
Authorization: Bearer <access_token>
```

**Response (200 OK):**
```json
{
    "booking_id": "uuid",
    "events": [
        {
            "event_type": "CREATED",
            "description": "Booking created",
            "actor_type": "USER",
            "created_at": "2024-01-20T10:30:00Z"
        },
        {
            "event_type": "PAYMENT_CONFIRMED",
            "description": "Payment confirmed and held in escrow",
            "actor_type": "SYSTEM",
            "created_at": "2024-01-20T10:32:00Z"
        }
    ]
}
```

---

## 6. Ride Endpoints

### 6.1 List Rides

```http
GET /api/v1/rides/
Authorization: Bearer <access_token>
Query Parameters:
    - origin: string
    - destination: string
    - departure_date: date
    - departure_time_gte: time
    - departure_time_lte: time
    - available_seats: number
```

**Response (200 OK):**
```json
{
    "count": 50,
    "results": [
        {
            "id": "uuid",
            "route_name": "Downtown Express",
            "origin": "New York",
            "destination": "Boston",
            "departure_time": "2024-02-01T08:00:00Z",
            "total_seats": 4,
            "available_seats": 2,
            "seat_price": "35.00",
            "currency": "USD",
            "status": "OPEN",
            "driver": {
                "id": "uuid",
                "first_name": "Mike",
                "avatar": "...",
                "trust_score": "85.00",
                "rating_count": 100
            },
            "vehicle": {
                "description": "Toyota Camry 2022",
                "color": "Silver"
            }
        }
    ]
}
```

### 6.2 Retrieve Ride

```http
GET /api/v1/rides/{ride_id}/
Authorization: Bearer <access_token>
```

### 6.3 Get Seat Availability

```http
GET /api/v1/rides/{ride_id}/seats/
Authorization: Bearer <access_token>
```

**Response (200 OK):**
```json
{
    "ride_id": "uuid",
    "total_seats": 4,
    "available_seats": 2,
    "seats": [
        {"seat_number": 1, "status": "AVAILABLE", "price": "35.00"},
        {"seat_number": 2, "status": "BOOKED", "price": "35.00"},
        {"seat_number": 3, "status": "AVAILABLE", "price": "35.00"},
        {"seat_number": 4, "status": "AVAILABLE", "price": "35.00"}
    ]
}
```

### 6.4 Book Seat

```http
POST /api/v1/rides/{ride_id}/book/
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "seat_number": 1,
    "pickup_stop_id": "uuid",
    "dropoff_stop_id": "uuid",
    "passenger_notes": "I have one suitcase",
    "luggage_count": 1,
    "payment_method": "CREDIT_CARD"
}
```

### 6.5 List My Rides (as Driver)

```http
GET /api/v1/rides/my_drives/
Authorization: Bearer <access_token>
Query Parameters:
    - status: SCHEDULED | OPEN | DEPARTED | IN_TRANSIT | COMPLETED | CANCELLED
```

### 6.6 List My Bookings (as Passenger)

```http
GET /api/v1/rides/my_bookings/
Authorization: Bearer <access_token>
```

### 6.7 Check In

```http
POST /api/v1/rides/{ride_id}/seats/{seat_booking_id}/check_in/
Authorization: Bearer <access_token>
```

### 6.8 Cancel Seat Booking

```http
POST /api/v1/rides/{ride_id}/seats/{seat_booking_id}/cancel/
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "reason": "Changed plans"
}
```

---

## 7. Contract Endpoints

### 7.1 Retrieve Contract

```http
GET /api/v1/contracts/{contract_id}/
Authorization: Bearer <access_token>
```

**Response (200 OK):**
```json
{
    "id": "uuid",
    "booking_id": "uuid",
    "version": 1,
    "status": "PENDING",
    "snapshot": {
        "booking": {...},
        "asset": {...},
        "pricing": {...},
        "terms": {...}
    },
    "jurisdiction": "US-NY",
    "cancellation_policy": "Full refund if cancelled 48 hours before...",
    "late_return_policy": "Late fee of $10/hour applies...",
    "damage_policy": "Tenant responsible for damages...",
    "owner_signature": null,
    "renter_signature": null,
    "generated_at": "2024-01-20T10:30:00Z"
}
```

### 7.2 Accept Contract

```http
POST /api/v1/contracts/{contract_id}/accept/
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "signature": {
        "signed_at": "2024-01-20T10:35:00Z",
        "ip_address": "192.168.1.1",
        "user_agent": "Mozilla/5.0..."
    }
}
```

### 7.3 Contract History

```http
GET /api/v1/contracts/{contract_id}/versions/
Authorization: Bearer <access_token>
```

---

## 8. Payment Endpoints

### 8.1 Retrieve Payment

```http
GET /api/v1/payments/{payment_id}/
Authorization: Bearer <access_token>
```

**Response (200 OK):**
```json
{
    "id": "uuid",
    "booking_id": "uuid",
    "amount": "118.00",
    "currency": "USD",
    "payment_method": "CREDIT_CARD",
    "status": "ESCROW",
    "card_last_four": "4242",
    "card_brand": "VISA",
    "escrow_held_at": "2024-01-20T10:32:00Z",
    "escrow_amount": "118.00",
    "escrow_released_at": null,
    "penalty_amount": "0.00",
    "refunded_amount": "0.00"
}
```

### 8.2 Request Refund

```http
POST /api/v1/payments/{payment_id}/refund/
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "amount": "59.00",
    "reason": "Partial cancellation"
}
```

---

## 9. Messaging Endpoints

### 9.1 List Threads

```http
GET /api/v1/messaging/threads/
Authorization: Bearer <access_token>
Query Parameters:
    - thread_type: INQUIRY | BOOKING | RIDE | DISPUTE | DIRECT | SUPPORT
    - status: OPEN | LOCKED | CLOSED
```

### 9.2 Create Thread

```http
POST /api/v1/messaging/threads/
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "thread_type": "INQUIRY",
    "subject": "Question about the apartment",
    "asset_id": "uuid",
    "initial_message": {
        "content": "Is the apartment available for check-in after 10pm?"
    }
}
```

### 9.3 Retrieve Thread

```http
GET /api/v1/messaging/threads/{thread_id}/
Authorization: Bearer <access_token>
```

**Response (200 OK):**
```json
{
    "id": "uuid",
    "thread_type": "INQUIRY",
    "subject": "Question about the apartment",
    "status": "OPEN",
    "participants": [...],
    "messages": [
        {
            "id": "uuid",
            "sender": {...},
            "content": "Is the apartment available for check-in after 10pm?",
            "created_at": "2024-01-20T10:00:00Z",
            "status": "READ"
        }
    ],
    "message_count": 5,
    "created_at": "2024-01-20T10:00:00Z"
}
```

### 9.4 Send Message

```http
POST /api/v1/messaging/threads/{thread_id}/messages/
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "content": "Yes, late check-in is available for a small fee.",
    "attachments": [
        {"file": "/media/..."}
    ]
}
```

### 9.5 Mark as Read

```http
POST /api/v1/messaging/threads/{thread_id}/read/
Authorization: Bearer <access_token>
```

### 9.6 Report Abuse

```http
POST /api/v1/messaging/threads/{thread_id}/report/
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "reason": "SPAM",
    "description": "This user is sending spam messages"
}
```

---

## 10. Notification Endpoints

### 10.1 List Notifications

```http
GET /api/v1/notifications/
Authorization: Bearer <access_token>
Query Parameters:
    - status: PENDING | SENT | READ | FAILED
    - category: BOOKING | RIDE | PAYMENT | MESSAGE | RATING | SYSTEM
```

### 10.2 Retrieve Notification

```http
GET /api/v1/notifications/{notification_id}/
Authorization: Bearer <access_token>
```

### 10.3 Mark as Read

```http
POST /api/v1/notifications/{notification_id}/read/
Authorization: Bearer <access_token>
```

### 10.4 Mark All as Read

```http
POST /api/v1/notifications/read_all/
Authorization: Bearer <access_token>
```

### 10.5 Notification Preferences

```http
GET /api/v1/notifications/preferences/
Authorization: Bearer <access_token>
```

**Response (200 OK):**
```json
{
    "email_enabled": true,
    "push_enabled": true,
    "sms_enabled": false,
    "categories": {
        "BOOKING": {"email": true, "push": true},
        "RIDE": {"email": true, "        "PAYMENT": {"email":push": true},
 true, "push": true},
        "MESSAGE": {"email": false, "push": true},
        "RATING": {"email": true, "push": false},
        "SYSTEM": {"email": true, "push": false}
    },
    "quiet_hours_enabled": true,
    "quiet_hours_start": "22:00",
    "quiet_hours_end": "08:00"
}
```

```http
PATCH /api/v1/notifications/preferences/
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "email_enabled": true,
    "push_enabled": true,
    "categories": {
        "BOOKING": {"email": true, "push": true}
    }
}
```

---

## 11. Rating Endpoints

### 11.1 List Ratings (for User)

```http
GET /api/v1/ratings/user/{user_id}/
Authorization: Bearer <access_token>
Query Parameters:
    - category: RENTER_TO_OWNER | OWNER_TO_RENTER | DRIVER_TO_PASSENGER | PASSENGER_TO_DRIVER
```

### 11.2 Create Rating

```http
POST /api/v1/ratings/
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "booking_id": "uuid",
    "ride_id": "uuid (optional)",
    "category": "RENTER_TO_OWNER",
    "overall_rating": 5,
    "reliability_rating": 5,
    "communication_rating": 4,
    "cleanliness_rating": 5,
    "timeliness_rating": 5,
    "asset_rating": 5,
    "title": "Great experience!",
    "comment": "The apartment was exactly as described..."
}
```

### 11.3 Retrieve Rating

```http
GET /api/v1/ratings/{rating_id}/
Authorization: Bearer <access_token>
```

### 11.4 Appeal Rating

```http
POST /api/v1/ratings/{rating_id}/appeal/
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "reason": "The rating is unfair because..."
}
```

---

## 12. Social Endpoints

### 12.1 Like Asset

```http
POST /api/v1/social/likes/assets/{asset_id}/
Authorization: Bearer <access_token>
```

### 12.2 Unlike Asset

```http
DELETE /api/v1/social/likes/assets/{asset_id}/
Authorization: Bearer <access_token>
```

### 12.3 List User Likes

```http
GET /api/v1/social/likes/
Authorization: Bearer <access_token>
```

### 12.4 Follow User

```http
POST /api/v1/social/follows/users/{user_id}/
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "entity_type": "OWNER"
}
```

### 12.5 Unfollow User

```http
DELETE /api/v1/social/follows/users/{user_id}/
Authorization: Bearer <access_token>
```

### 12.6 List Followers

```http
GET /api/v1/social/followers/
Authorization: Bearer <access_token>
```

### 12.7 List Following

```http
GET /api/v1/social/following/
Authorization: Bearer <access_token>
```

---

## 13. RBAC Admin Endpoints

### 13.1 List Users (Admin)

```http
GET /api/v1/admin/users/
Authorization: Bearer <access_token> (requires ADMIN role)
Query Parameters:
    - is_active: boolean
    - is_blocked: boolean
    - role: string
    - search: string
```

### 13.2 Ban User (Admin)

```http
POST /api/v1/admin/users/{user_id}/ban/
Authorization: Bearer <access_token> (requires ADMIN role)
Content-Type: application/json

{
    "reason": "Violation of terms of service",
    "justification": "User has been reported for fraudulent activity"
}
```

### 13.3 Unban User (Admin)

```http
POST /api/v1/admin/users/{user_id}/unban/
Authorization: Bearer <access_token> (requires ADMIN role)
Content-Type: application/json

{
    "justification": "User has resolved the issues"
}
```

### 13.4 Verify Asset (Admin)

```http
POST /api/v1/admin/assets/{asset_id}/verify/
Authorization: Bearer <access_token> (requires VERIFIER role)
Content-Type: application/json

{
    "status": "VERIFIED",
    "notes": "Asset has been verified and approved"
}
```

### 13.5 View Audit Logs (Admin)

```http
GET /api/v1/admin/audit-logs/
Authorization: Bearer <access_token> (requires AUDIT_VIEW role)
Query Parameters:
    - actor_id: uuid
    - action: string
    - resource_type: string
    - start_date: date
    - end_date: date
```

### 13.6 Assign Role (Admin)

```http
POST /api/v1/admin/users/{user_id}/roles/
Authorization: Bearer <access_token> (requires ROLE_MANAGE role)
Content-Type: application/json

{
    "role": "MODERATOR",
    "scope_type": "",
    "scope_id": null,
    "expires_at": "2024-12-31T23:59:59Z"
}
```

---

## 14. Error Responses

### 14.1 Bad Request (400)

```json
{
    "error": "VALIDATION_ERROR",
    "message": "Invalid request data",
    "details": {
        "field_name": ["This field is required."]
    }
}
```

### 14.2 Unauthorized (401)

```json
{
    "error": "UNAUTHORIZED",
    "message": "Authentication required"
}
```

### 14.3 Forbidden (403)

```json
{
    "error": "FORBIDDEN",
    "message": "You don't have permission to access this resource"
}
```

### 14.4 Not Found (404)

```json
{
    "error": "NOT_FOUND",
    "message": "Resource not found"
}
```

### 14.5 Conflict (409)

```json
{
    "error": "CONFLICT",
    "message": "Resource conflict",
    "details": {
        "reason": "Asset is already booked for this time slot"
    }
}
```

### 14.6 Too Many Requests (429)

```json
{
    "error": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests",
    "retry_after": 60,
    "limit": 100,
    "remaining": 0
}
```

### 14.7 Internal Server Error (500)

```json
{
    "error": "INTERNAL_ERROR",
    "message": "An unexpected error occurred",
    "request_id": "uuid"
}
```
