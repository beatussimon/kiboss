# End-to-End Use Case Walkthrough for KIBOSS

This document walks through key user scenarios in KIBOSS, showing how components interact.

---

## 1. User Registration & Onboarding

### 1.1 Registration Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        USER REGISTRATION FLOW                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   NEW USER                                                                    │
│      │                                                                        │
│      ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 1. Access Registration Page         │                                   │
│   │    GET /register                    │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 2. Submit Registration Form         │                                   │
│   │    POST /api/v1/auth/register/      │                                   │
│   │    {                                │                                   │
│   │      "email": "user@example.com",  │                                   │
│   │      "password": "secure123",       │                                   │
│   │      "first_name": "John",          │                                   │
│   │      "last_name": "Doe"             │                                   │
│   │    }                                │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 3. Validate Input                   │                                   │
│   │    - Check email format             │                                   │
│   │    - Check password strength        │                                   │
│   │    - Check email uniqueness         │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 4. Create User Record               │                                   │
│   │    - Create User in DB              │                                   │
│   │    - Create UserProfile             │                                   │
│   │    - Set trust_score = 50.00        │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 5. Send Verification Email          │                                   │
│   │    - Generate verification token    │                                   │
│   │    - Queue email task (Celery)     │                                   │
│   │    - Send to user email            │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 6. Create Audit Log                 │                                   │
│   │    - Log USER_CREATED action        │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 7. Return Response                  │                                   │
│   │    201 Created                      │                                   │
│   │    {                                │                                   │
│   │      "message": "Registration       │                                   │
│   │       successful",                  │                                   │
│   │      "user_id": "uuid"              │                                   │
│   │    }                                │                                   │
│   └─────────────────────────────────────┘                                   │
│                                                                              │
│   RESULT: User account created, email verification pending                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Email Verification Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      EMAIL VERIFICATION FLOW                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   USER CLICKS VERIFICATION LINK                                              │
│      │                                                                        │
│      ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ GET /verify-email?token=xxx          │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 1. Validate Token                   │                                   │
│   │    - Check token exists             │                                   │
│   │    - Check token not expired        │                                   │
│   │    - Get user from token            │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 2. Update User                      │                                   │
│   │    - Set is_email_verified = true   │                                   │
│   │    - Set email_verified_at = now   │                                   │
│   │    - Delete verification token      │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 3. Create Audit Log                 │                                   │
│   │    - Log EMAIL_VERIFIED action      │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 4. Redirect to Dashboard            │                                   │
│   │    /dashboard?verified=true         │                                   │
│   └─────────────────────────────────────┘                                   │
│                                                                              │
│   RESULT: User email verified, can access full features                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Asset Creation & Listing

### 2.1 Asset Creation Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ASSET CREATION FLOW                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   REGISTERED USER                                                            │
│      │                                                                        │
│      ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 1. Access Create Asset Page         │                                   │
│   │    GET /assets/new                  │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 2. Submit Asset Form                │                                   │
│   │    POST /api/v1/assets/             │                                   │
│   │    {                                │                                   │
│   │      "name": "Downtown Office",    │                                   │
│   │      "asset_type": "ROOM",          │                                   │
│   │      "description": "...",          │                                   │
│   │      "address": "123 Main St",      │                                   │
│   │      "pricing_rules": [...],        │                                   │
│   │      "availability_rules": [...]    │                                   │
│   │    }                                │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 3. Validate Input                   │                                   │
│   │    - Check all required fields     │                                   │
│   │    - Validate pricing rules         │                                   │
│   │    - Validate availability rules    │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 4. Create Asset Record              │                                   │
│   │    - Create Asset in DB            │                                   │
│   │    - Create AssetJurisdiction      │                                   │
│   │    - Create AssetPricing records   │                                   │
│   │    - Create AssetAvailability      │                                   │
│   │    - Create AssetCapacity records  │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 5. Assign OWNER Role                │                                   │
│   │    - Create UserRole record         │                                   │
│   │    - scope_type = "ASSET"           │                                   │
│   │    - scope_id = asset.id           │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 6. Update User Profile              │                                   │
│   │    - Increment total_listings      │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 7. Create Audit Log                 │                                   │
│   │    - Log ASSET_CREATED action      │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 8. Cache Asset                      │                                   │
│   │    - Store in Redis cache          │                                   │
│   │    - key: asset:{id}               │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 9. Return Response                  │                                   │
│   │    201 Created                      │                                   │
│   │    { "id": "uuid", "status":       │                                   │
│   │     "UNVERIFIED" }                  │                                   │
│   └─────────────────────────────────────┘                                   │
│                                                                              │
│   RESULT: Asset created, verification pending                                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Asset Verification Flow (Admin)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ASSET VERIFICATION FLOW                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ADMIN USER                                                                  │
│      │                                                                        │
│      ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 1. Access Unverified Assets List    │                                   │
│   │    GET /admin/assets?status=        │                                   │
│   │     UNVERIFIED                       │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 2. Review Asset Details             │                                   │
│   │    GET /api/v1/assets/{id}/        │                                   │
│   │    - View photos                    │                                   │
│   │    - View description               │                                   │
│   │    - View location                  │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 3. Submit Verification Decision    │                                   │
│   │    POST /api/v1/admin/assets/{id}   │                                   │
│   │    /verify/                         │                                   │
│   │    {                                │                                   │
│   │      "status": "VERIFIED",          │                                   │
│   │      "notes": "All checks passed"   │                                   │
│   │    }                                │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 4. Validate Admin Permission        │                                   │
│   │    - Check ASSET_VERIFY permission │                                   │
│   │    - Check justification provided   │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 5. Update Asset Record              │                                   │
│   │    - Set verification_status =     │                                   │
│   │     "VERIFIED"                      │                                   │
│   │    - Set verified_at = now         │                                   │
│   │    - Set verified_by = admin       │                                   │
│   │    - Add verification notes        │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 6. Send Notification                │                                   │
│   │    - Notify asset owner            │                                   │
│   │    - "Your asset has been          │                                   │
│   │     verified!"                      │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 7. Create Audit Log                 │                                   │
│   │    - Log ASSET_VERIFIED action     │                                   │
│   │    - Include admin justification    │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 8. Return Response                  │                                   │
│   │    200 OK                           │                                   │
│   └─────────────────────────────────────┘                                   │
│                                                                              │
│   RESULT: Asset verified, visible in search results                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Complete Booking Flow

### 3.1 Booking Creation & Payment

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      BOOKING CREATION FLOW                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   RENTER USER                                                                 │
│      │                                                                        │
│      ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 1. Search for Asset                 │                                   │
│   │    GET /api/v1/assets/?city=NYC    │                                   │
│   │    - View search results           │                                   │
│   │    - Filter by date, price, type   │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 2. Check Availability               │                                   │
│   │    GET /api/v1/assets/{id}/         │                                   │
│   │    availability/?start_time=...    │                                   │
│   │    &end_time=...                   │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 3. Receive Availability Response    │                                   │
│   │    {                                │                                   │
│   │      "is_available": true,         │                                   │
│   │      "available_quantity": 4,       │                                   │
│   │      "price_quote": {               │                                   │
│   │        "total": 118.00,            │                                   │
│   │        "breakdown": {...}           │                                   │
│   │      }                              │                                   │
│   │    }                                │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 4. Submit Booking Request           │                                   │
│   │    POST /api/v1/bookings/          │                                   │
│   │    {                                │                                   │
│   │      "asset_id": "uuid",           │                                   │
│   │      "start_time": "2024-02-01     │                                   │
│   │       T10:00:00Z",                 │                                   │
│   │      "end_time": "2024-02-01       │                                   │
│   │       T12:00:00Z",                 │                                   │
│   │      "quantity": 2                 │                                   │
│   │    }                                │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 5. Acquire Asset Lock               │                                   │
│   │    Redis: SET lock:asset:{id}      │                                   │
│   │    NX EX 30                         │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 6. Check Availability Again         │                                   │
│   │    - Query DB for overlapping      │                                   │
│   │      bookings                      │                                   │
│   │    - Calculate available quantity  │                                   │
│   │    - Validate against requested    │                                   │
│   │      quantity                      │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ├───── Not available? ──────► Return 409 Conflict                 │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 7. Calculate Price                 │                                   │
│   │    - Apply pricing rules           │                                   │
│   │    - Calculate service fee         │                                   │
│   │    - Calculate taxes               │                                   │
│   │    - Generate price breakdown      │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 8. Create PENDING Booking          │                                   │
│   │    - Create Booking record         │                                   │
│   │    - status = PENDING              │                                   │
│   │    - Set expires_at = now + 15min  │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 9. Create Contract Snapshot        │                                   │
│   │    - Create Contract record        │                                   │
│   │    - status = PENDING              │                                   │
│   │    - Store booking snapshot        │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 10. Initiate Payment               │                                   │
│   │    - Create Payment record        │                                   │
│   │    - Zenopay authorize (simulate) │                                   │
│   │    - status = AUTHORIZED          │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 11. Schedule Expiry Task           │                                   │
│   │    Celery: expire_pending_bookings │                                   │
│   │    - eta = now + 15 minutes       │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 12. Release Lock                    │                                   │
│   │    Redis: DEL lock:asset:{id}      │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 13. Send Notifications             │                                   │
│   │    - Notify renter: booking        │                                   │
│   │      pending confirmation         │                                   │
│   │    - Notify owner: new booking    │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 14. Return Response                 │                                   │
│   │    201 Created                      │                                   │
│   │    {                                │                                   │
│   │      "id": "uuid",                │                                   │
│   │      "status": "PENDING",         │                                   │
│   │      "expires_at": "...",         │                                   │
│   │      "total_price": 118.00        │                                   │
│   │    }                                │                                   │
│   └─────────────────────────────────────┘                                   │
│                                                                              │
│   RESULT: Booking created, awaiting payment confirmation                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Payment & Contract Acceptance

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                  PAYMENT CONFIRMATION & CONTRACT ACCEPTANCE                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   RENTER USER (after booking created)                                         │
│      │                                                                        │
│      ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 1. Complete Payment                 │                                   │
│   │    POST /api/v1/bookings/{id}/     │                                   │
│   │    confirm_payment/                 │                                   │
│   │    {                                │                                   │
│   │      "payment_intent_id": "pi_..." │                                   │
│   │    }                                │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 2. Process Payment                  │                                   │
│   │    - Zenopay capture (simulate)    │                                   │
│   │    - Update payment status =      │                                   │
│   │      ESCROW                         │                                   │
│   │    - Set escrow_held_at = now     │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 3. Update Booking Status           │                                   │
│   │    - Transition PENDING →          │                                   │
│   │      CONFIRMED                     │                                   │
│   │    - Create transition record     │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 4. Create Timeline Event           │                                   │
│   │    - Log PAYMENT_CONFIRMED        │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 5. Notify Owner                    │                                   │
│   │    - Booking payment confirmed     │                                   │
│   │    - Request contract acceptance  │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 6. Owner Accepts Contract          │                                   │
│   │    POST /api/v1/contracts/{id}/    │                                   │
│   │    accept/                         │                                   │
│   │    {                                │                                   │
│   │      "signature": {...}            │                                   │
│   │    }                                │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 7. Update Contract                 │                                   │
│   │    - Store owner signature         │                                   │
│   │    - Set owner_accepted_at = now   │                                   │
│   │    - status = ACCEPTED             │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 8. Notify Renter to Accept         │                                   │
│   │    - Contract awaiting your        │                                   │
│   │      signature                     │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 9. Renter Accepts Contract         │                                   │
│   │    POST /api/v1/contracts/{id}/    │                                   │
│   │    accept/                         │                                   │
│   │    {                                │                                   │
│   │      "signature": {...}            │                                   │
│   │    }                                │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 10. Update Contract Status         │                                   │
│   │    - Store renter signature       │                                   │
│   │    - Set renter_accepted_at = now │                                   │
│   │    - status = EXECUTED            │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 11. Notify Both Parties            │                                   │
│   │    - Booking fully confirmed       │                                   │
│   │    - Send booking details         │                                   │
│   │    - Send reminder for start time │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 12. Return Final Response         │                                   │
│   │    200 OK                          │                                   │
│   │    {                                │                                   │
│   │      "status": "CONFIRMED",       │                                   │
│   │      "contract_status":           │                                   │
│   │       "EXECUTED"                  │                                   │
│   │    }                                │                                   │
│   └─────────────────────────────────────┘                                   │
│                                                                              │
│   RESULT: Booking confirmed, contract executed, payment in escrow              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Ride-Sharing Complete Flow

### 4.1 Ride Creation & Seat Booking

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    RIDE CREATION & SEAT BOOKING                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   DRIVER USER                                                                 │
│      │                                                                        │
│      ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 1. Create Ride                      │                                   │
│   │    POST /api/v1/rides/             │                                   │
│   │    {                                │                                   │
│   │      "route_name": "Downtown      │                                   │
│   │       Express",                    │                                   │
│   │      "origin": "NYC",              │                                   │
│   │      "destination": "Boston",      │                                   │
│   │      "departure_time": "2024-02-01 │                                   │
│   │       T08:00:00Z",                 │                                   │
│   │      "total_seats": 4,             │                                   │
│   │      "seat_price": 35.00,          │                                   │
│   │      "stops": [...]                │                                   │
│   │    }                                │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 2. Create Ride Record               │                                   │
│   │    - status = SCHEDULED            │                                   │
│   │    - Set confirmed_seats = 0      │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 3. Create Ride Stops                │                                   │
│   │    - Create RideStop records       │                                   │
│   │    - Set stop_order for each      │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 4. Return Response                  │                                   │
│   │    201 Created                      │                                   │
│   └─────────────────────────────────────┘                                   │
│                                                                              │
│   ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│   PASSENGER USER                                                             │
│      │                                                                        │
│      ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 1. Search for Rides                 │                                   │
│   │    GET /api/v1/rides/?origin=NYC   │                                   │
│   │    &destination=Boston             │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 2. View Ride Details               │                                   │
│   │    GET /api/v1/rides/{id}/        │                                   │
│   │    - View seat availability       │                                   │
│   │    - View stops and times         │                                   │
│   │    - View driver info             │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 3. Check Seat Availability         │                                   │
│   │    GET /api/v1/rides/{id}/seats/  │                                   │
│   │    Response:                        │                                   │
│   │    {                                │                                   │
│   │      "available_seats": 3,        │                                   │
│   │      "seats": [                   │                                   │
│   │        {"seat": 1, "status":      │                                   │
│   │         "AVAILABLE"},              │                                   │
│   │        {"seat": 2, "status":      │                                   │
│   │         "BOOKED"}, ...            │                                   │
│   │      ]                              │                                   │
│   │    }                                │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 4. Book Seat                       │                                   │
│   │    POST /api/v1/rides/{id}/book/  │                                   │
│   │    {                                │                                   │
│   │      "seat_number": 1,            │                                   │
│   │      "pickup_stop_id": "uuid",     │                                   │
│   │      "dropoff_stop_id": "uuid"    │                                   │
│   │    }                                │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 5. Acquire Seat Lock               │                                   │
│   │    Redis: SET lock:seat:{ride}:1  │                                   │
│   │    NX EX 30                         │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 6. Validate Seat Availability      │                                   │
│   │    - Query DB for seat 1 status   │                                   │
│   │    - Check if RESERVED or         │                                   │
│   │      CONFIRMED                     │                                   │
│   │    - Check ride capacity          │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ├───── Seat taken? ──────► Return 409 Conflict                    │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 7. Create Seat Booking             │                                   │
│   │    - Create SeatBooking record    │                                   │
│   │    - status = RESERVED            │                                   │
│   │    - Reserve seat 1               │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 8. Update Ride Seat Count          │                                   │
│   │    - Increment confirmed_seats    │                                   │
│   │    - Update ride in DB            │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 9. Process Payment                 │                                   │
│   │    - Create Payment record        │                                   │
│   │    - Zenopay authorize & capture  │                                   │
│   │    - status = ESCROW              │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 10. Update Seat Status             │                                   │
│   │    - status = CONFIRMED           │                                   │
│   │    - Store payment reference      │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 11. Release Seat Lock              │                                   │
│   │    Redis: DEL lock:seat:{ride}:1   │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 12. Create Contract                │                                   │
│   │    - Generate ride-specific       │                                   │
│   │      contract                     │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 13. Send Notifications             │                                   │
│   │    - Notify passenger: booking    │                                   │
│   │      confirmed                     │                                   │
│   │    - Notify driver: new passenger │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 14. Return Response                │                                   │
│   │    201 Created                     │                                   │
│   └─────────────────────────────────────┘                                   │
│                                                                              │
│   RESULT: Seat booked, payment in escrow, contract generated                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Dispute Resolution Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DISPUTE RESOLUTION FLOW                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   RENTER USER (after rental issue)                                            │
│      │                                                                        │
│      ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 1. Submit Dispute                   │                                   │
│   │    POST /api/v1/bookings/{id}/     │                                   │
│   │    dispute/                         │                                   │
│   │    {                                │                                   │
│   │      "reason": "DAMAGE",           │                                   │
│   │      "description": "Apartment    │                                   │
│   │       had significant mold...",   │                                   │
│   │      "disputed_amount": 500.00,   │                                   │
│   │      "evidence": [                 │                                   │
│   │        {"type": "IMAGE",           │                                   │
│   │         "url": "/media/..."}       │                                   │
│   │      ]                              │                                   │
│   │    }                                │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 2. Validate Dispute                 │                                   │
│   │    - Check booking is eligible    │                                   │
│   │    - Check dispute not already    │                                   │
│   │      exists                        │                                   │
│   │    - Validate evidence            │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 3. Create Dispute Record           │                                   │
│   │    - Create Dispute record        │                                   │
│   │    - status = OPEN                 │                                   │
│   │    - Freeze payment in escrow    │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 4. Update Booking Status           │                                   │
│   │    - Transition to DISPUTED       │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 5. Notify Parties                   │                                   │
│   │    - Notify renter: dispute filed │                                   │
│   │    - Notify owner: dispute        │                                   │
│   │      received                      │                                   │
│   │    - Notify support team          │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 6. Support Team Reviews            │                                   │
│   │    - Gather additional evidence   │                                   │
│   │    - Interview both parties        │                                   │
│   │    - status = EVIDENCE_COLLECTION │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 7. Resolution Decision            │                                   │
│   │    POST /api/v1/admin/disputes/    │                                   │
│   │    {id}/resolve/                   │                                   │
│   │    {                                │                                   │
│   │      "resolution": "REFUND_       │                                   │
│   │       PARTIAL",                     │                                   │
│   │      "notes": "Owner responsible  │                                   │
│   │       for 50% refund",            │                                   │
│   │      "refund_amount": 250.00      │                                   │
│   │    }                                │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 8. Process Resolution              │                                   │
│   │    - If refund: payment.refund()  │                                   │
│   │    - If release:                  │                                   │
│   │      payment.release_from_escrow() │                                   │
│   │    - Update dispute status =      │                                   │
│   │      RESOLVED                       │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 9. Update Trust Scores             │                                   │
│   │    - Adjust renter trust if       │                                   │
│   │      disputed fairly               │                                   │
│   │    - Adjust owner trust if        │                                   │
│   │      responsible for issue        │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 10. Notify Parties                  │                                   │
│   │    - Send resolution details      │                                   │
│   │    - Send refund/payment info    │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 11. Create Audit Log               │                                   │
│   │    - Log DISPUTE_RESOLVED action  │                                   │
│   │    - Include resolution details   │                                   │
│   └──────┬──────────────────────────────┘                                   │
│                                                                              │
│   RESULT: Dispute resolved, payment processed, trust scores updated          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Rating Submission Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        RATING SUBMISSION FLOW                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   USER (after completed booking)                                             │
│      │                                                                        │
│      ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 1. Check Rating Eligibility         │                                   │
│   │    GET /api/v1/ratings/eligible/   │                                   │
│   │    Response:                        │                                   │
│   │    [                                │                                   │
│   │      {                              │                                   │
│   │        "booking_id": "uuid",       │                                   │
│   │        "reviewee": {...},         │                                   │
│   │        "can_rate": true           │                                   │
│   │      }                              │                                   │
│   │    ]                                │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 2. Submit Rating                   │                                   │
│   │    POST /api/v1/ratings/          │                                   │
│   │    {                                │                                   │
│   │      "booking_id": "uuid",       │                                   │
│   │      "category": "RENTER_TO_     │                                   │
│   │       OWNER",                      │                                   │
│   │      "overall_rating": 5,        │                                   │
│   │      "reliability_rating": 5,     │                                   │
│   │      "communication_rating": 4,  │                                   │
│   │      "cleanliness_rating": 5,    │                                   │
│   │      "timeliness_rating": 5,     │                                   │
│   │      "comment": "Great host!     │                                   │
│   │       Would definitely stay      │                                   │
│   │       again.",                     │                                   │
│   │      "title": "Perfect stay"     │                                   │
│   │    }                                │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 3. Validate Rating                 │                                   │
│   │    - Check booking completed      │                                   │
│   │    - Check rating not duplicate  │                                   │
│   │    - Check ratings within 1-5    │                                   │
│   │    - Check within 14-day window  │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 4. Create Rating Record            │                                   │
│   │    - Create Rating record         │                                   │
│   │    - status = SUBMITTED           │                                   │
│   │    - is_mutually_revealed = false │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 5. Check Mutual Rating             │                                   │
│   │    - Query if other party also    │                                   │
│   │      rated                        │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ├───── Other party rated ─────┤                                     │
│          │                             │                                     │
│          ▼                             ▼                                     │
│   ┌─────────────────────┐    ┌─────────────────────┐                          │
│   │ Reveal Both Ratings│    │ Wait for Other      │                          │
│   │ - Update both to   │    │ Party to Rate      │                          │
│   │   REVEALED        │    │ - Status stays      │                          │
│   │ - Notify both      │    │   SUBMITTED        │                          │
│   │ - Update trust    │    │ - Schedule reveal  │                          │
│   │   scores          │    │   when other rates │                          │
│   └─────────────────────┘    └─────────────────────┘                          │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 6. Return Response                 │                                   │
│   │    201 Created                     │                                   │
│   │    {                                │                                   │
│   │      "id": "uuid",               │                                   │
│   │      "status": "SUBMITTED"       │                                   │
│   │    }                                │                                   │
│   └─────────────────────────────────────┘                                   │
│                                                                              │
│   RESULT: Rating submitted, revealed to other party if they've rated too    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. System Error Recovery Flows

### 7.1 Payment Failure Recovery

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      PAYMENT FAILURE RECOVERY                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   SCENARIO: User's card is declined during booking                          │
│                                                                              │
│   STEP 1: Payment Attempt                                                   │
│   ┌─────────────────────────────────────┐                                   │
│   │ POST /api/v1/bookings/{id}/       │                                   │
│   │ confirm_payment/                 │                                   │
│   │ Response: 402 Payment Required   │                                   │
│   │ {                                │                                   │
│   │   "error": "CARD_DECLINED",     │                                   │
│   │   "message": "Your card was     │                                   │
│   │    declined"                     │                                   │
│   │ }                                │                                   │
│   └─────────────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 2. User Tries Different Card      │                                   │
│   │    - System keeps booking in       │                                   │
│   │      PENDING state                 │                                   │
│   │    - Booking expires in 15 min   │                                   │
│   └──────┬──────────────────────────────┘                                   │
│          │                                                                        │
│          ▼                                                                        │
│   ┌─────────────────────────────────────┐                                   │
│   │ 3. Successful Payment             │                                   │
│   │    - Payment captured successfully│                                   │
│   │    - Booking transitions to       │                                   │
│   │      CONFIRMED                     │                                   │
│   └─────────────────────────────────────┘                                   │
│                                                                              │
│   ALTERNATIVE: Booking Expires Before Payment                               │
│   ┌─────────────────────────────────────┐                                   │
│   │ Celery task runs (every 1 min)   │                                   │
│   │ - Find PENDING bookings > 15 min  │                                   │
│   │ - Transition to EXPIRED           │                                   │
│   │ - Release asset availability      │                                   │
│   │ - Send notification to user      │                                   │
│   └─────────────────────────────────────┘                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Concurrent Booking Race Condition

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                 CONCURRENT BOOKING PREVENTION                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   User A and User B both try to book same asset at same time                 │
│                                                                              │
│   User A                          User B                                     │
│      │                               │                                       │
│      │  Acquire Redis lock          │                                       │
│      │◄──────────────────────────────│                                       │
│      │  SUCCESS                      │                                       │
│      │                               │  Acquire Redis lock                  │
│      │                               │◄─────────────────────────────────────│
│      │                               │  FAIL (already held)                 │
│      │                               │                                       │
│      │  Check availability          │  Retry with backoff                  │
│      │◄──────────────────────────────│                                       │
│      │  AVAILABLE                    │                                       │
│      │                               │  Acquire Redis lock (retry 2)       │
│      │                               │◄─────────────────────────────────────│
│      │                               │  SUCCESS                             │
│      │                               │                                       │
│      │  Create booking              │  Check availability                  │
│      │◄──────────────────────────────│◄─────────────────────────────────────│
│      │  SUCCESS                      │  NOT AVAILABLE (User A got it)       │
│      │                               │                                       │
│      │  Release lock                │  Release lock                        │
│      │◄──────────────────────────────│◄─────────────────────────────────────│
│      │                               │                                       │
│      │                               │  Return error to User B:             │
│      │                               │  "Asset no longer available"          │
│      │                               │                                       │
│   RESULT: User A gets booking, User B gets appropriate error                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```
