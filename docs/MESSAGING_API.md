# Messaging API Documentation

## Overview
The Messaging API provides endpoints for managing message threads and messages between users in the KIBOSS platform.

## Base URL
```
/api/v1/messages/
```

## Authentication
All endpoints require JWT authentication. Include the token in the Authorization header:
```
Authorization: Bearer <access_token>
```

## Endpoints

### 1. List Threads
Get all threads for the authenticated user.

**Endpoint:** `GET /threads/`

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| thread_type | string | Filter by thread type (INQUIRY, BOOKING, RIDE, DISPUTE, DIRECT, SUPPORT) |
| status | string | Filter by status (OPEN, LOCKED, CLOSED) |

**Response:**
```json
{
  "count": 10,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "uuid",
      "thread_type": "DIRECT",
      "subject": "Hello",
      "status": "OPEN",
      "participants": [
        {
          "id": "uuid",
          "email": "user@example.com",
          "first_name": "John",
          "last_name": "Doe"
        }
      ],
      "message_count": 5,
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-02T00:00:00Z"
    }
  ]
}
```

---

### 2. Create Thread
Create a new message thread.

**Endpoint:** `POST /threads/`

**Request Body:**
```json
{
  "thread_type": "DIRECT",
  "subject": "Optional subject",
  "booking": "uuid (optional)",
  "ride": "uuid (optional)"
}
```

**Response:** Returns the created thread object

---

### 3. Create Direct Message Thread
Create or get an existing direct message thread with another user.

**Endpoint:** `POST /threads/create_direct/`

**Request Body:**
```json
{
  "user_id": "uuid of target user",
  "subject": "optional subject"
}
```

**Response:** Returns existing or newly created thread

---

### 4. Get Thread Details
Get details of a specific thread.

**Endpoint:** `GET /threads/{thread_id}/`

**Response:**
```json
{
  "id": "uuid",
  "thread_type": "DIRECT",
  "subject": "Hello",
  "status": "OPEN",
  "participants": [...],
  "message_count": 5,
  "messages": [
    {
      "id": "uuid",
      "sender": {...},
      "content": "Hello!",
      "content_type": "text/plain",
      "status": "READ",
      "created_at": "2024-01-01T00:00:00Z",
      "attachments": [...]
    }
  ],
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-02T00:00:00Z"
}
```

---

### 5. Get Thread Messages (Paginated)
Get messages in a thread with pagination.

**Endpoint:** `GET /threads/{thread_id}/message_list/`

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| page | integer | 1 | Page number |
| page_size | integer | 20 | Number of items per page (max 100) |

**Response:**
```json
{
  "count": 100,
  "next": "http://api/v1/messages/threads/{id}/message_list/?page=2",
  "previous": null,
  "results": [
    {
      "id": "uuid",
      "sender": {"id": "uuid", "email": "..."},
      "content": "Hello!",
      "content_type": "text/plain",
      "status": "READ",
      "created_at": "2024-01-01T00:00:00Z",
      "attachments": []
    }
  ]
}
```

---

### 6. Send Message
Send a message to a thread.

**Endpoint:** `POST /threads/{thread_id}/messages/`

**Request Body:**
```json
{
  "content": "Hello, how are you?",
  "content_type": "text/plain"
}
```

**Response:** Returns the created message object

---

### 7. Add Participant
Add a participant to an existing thread.

**Endpoint:** `POST /threads/{thread_id}/add_participant/`

**Request Body:**
```json
{
  "user_id": "uuid of user to add"
}
```

**Response:** Returns updated thread object

---

### 8. Mark Messages as Read
Mark all messages in a thread as read.

**Endpoint:** `POST /threads/{thread_id}/read/`

**Response:** Returns success status

---

### 9. Lock Thread
Lock a thread (prevents new messages).

**Endpoint:** `POST /threads/{thread_id}/lock/`

**Response:** Returns updated thread object

---

### 10. Unlock Thread
Unlock a thread.

**Endpoint:** `POST /threads/{thread_id}/unlock/`

**Response:** Returns updated thread object

---

### 11. Leave Thread
Leave a thread (remove yourself as participant).

**Endpoint:** `POST /threads/{thread_id}/leave/`

**Response:** Returns success status

---

### 12. Upload Attachment
Upload an attachment to a message.

**Endpoint:** `POST /attachments/`

**Content-Type:** multipart/form-data

**Request Body:**
| Field | Type | Description |
|-------|------|-------------|
| message | uuid | ID of the message to attach to |
| file | file | The file to upload |
| file_type | string | Type: IMAGE, DOCUMENT, VIDEO, AUDIO |

**Response:**
```json
{
  "id": "uuid",
  "file": "/media/message_attachments/2024/01/file.pdf",
  "file_type": "DOCUMENT",
  "file_name": "document.pdf",
  "file_size": 1024,
  "is_safe": true,
  "created_at": "2024-01-01T00:00:00Z"
}
```

---

### 13. Mark Single Message as Read
Mark a specific message as read.

**Endpoint:** `POST /messages/{message_id}/mark_read/`

**Response:** Returns updated message object

---

### 14. Delete Message
Soft delete a message (only sender can delete).

**Endpoint:** `POST /messages/{message_id}/delete/`

**Response:** Returns success status

---

## Thread Types
- **INQUIRY**: Pre-booking inquiry about an asset
- **BOOKING**: Discussion related to a booking
- **RIDE**: Discussion related to a ride
- **DISPUTE**: Dispute resolution conversation
- **DIRECT**: Direct message between two users
- **SUPPORT**: Support conversation

## Thread Status
- **OPEN**: Thread is active and accepts new messages
- **LOCKED**: Thread is locked, no new messages allowed
- **CLOSED**: Thread is closed
- **ARCHIVED**: Thread is archived

## Message Status
- **SENT**: Message has been sent
- **DELIVERED**: Message has been delivered
- **READ**: Message has been read

## Error Responses

### 401 Unauthorized
```json
{
  "detail": "Authentication credentials were not provided."
}
```

### 403 Forbidden
```json
{
  "error": "You are not a participant of this thread"
}
```

### 404 Not Found
```json
{
  "detail": "Not found."
}
```

### 400 Bad Request
```json
{
  "error": "Thread is locked"
}
```

## Contextual Messaging

### Create Contextual Thread
Create or get a thread linked to a specific context (listing, booking, or ride).

**Endpoint:** `POST /threads/create_contextual/`

**Request Body:**
```json
{
  "target_user_id": "uuid of the user to contact",
  "thread_type": "INQUIRY|BOOKING|RIDE|DISPUTE|DIRECT",
  "subject": "optional subject line",
  "listing_id": "optional uuid of the asset/listing",
  "booking_id": "optional uuid of the booking",
  "ride_id": "optional uuid of the ride"
}
```

**Response:** Returns the existing thread if one exists with the same context, or creates a new one.

**Use Cases:**
- Contact Seller on a listing: `thread_type: INQUIRY`, `listing_id: <asset-id>`
- Message about a booking: `thread_type: BOOKING`, `booking_id: <booking-id>`
- Message about a ride: `thread_type: RIDE`, `ride_id: <ride-id>`

## Rate Limiting
- Users are limited to 100 messages per hour
- Direct messages between users are rate-limited to prevent spam

## File Upload Restrictions
- Maximum file size: 10MB
- Supported types: Images (jpg, png, gif), Documents (pdf, doc, docx, txt), Videos, Audio
- All files are scanned for safety
