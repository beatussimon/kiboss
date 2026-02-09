# Step 3: Booking & Ride Algorithms

This document describes the core algorithms used in the KIBOSS booking engine and ride-sharing module.

---

## 1. Booking Algorithm

### 1.1 Booking Creation Algorithm

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     BOOKING CREATION ALGORITHM                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   FUNCTION: create_booking(renter_id, asset_id, start_time, end_time,      │
│                           quantity, payment_method)                         │
│                                                                              │
│   INPUT:                                                                     │
│   • renter_id: UUID of the user making the booking                          │
│   • asset_id: UUID of the asset being booked                                │
│   • start_time: datetime when rental begins                                 │
│   • end_time: datetime when rental ends                                     │
│   • quantity: number of units/seats                                         │
│   • payment_method: payment information                                    │
│                                                                              │
│   OUTPUT: booking_id or error                                               │
│                                                                              │
│   ALGORITHM:                                                                │
│   ──────────                                                                │
│                                                                              │
│   1. VALIDATE INPUT                                                         │
│      1.1. Check renter exists and is active                                │
│      1.2. Check asset exists and is active                                 │
│      1.3. Verify renter is not the owner (no self-booking)                 │
│      1.4. Check renter is not blocked                                      │
│      1.5. Validate start_time < end_time                                   │
│      1.6. Check start_time is in the future                               │
│      1.7. Validate quantity >= 1                                          │
│                                                                              │
│   2. ACQUIRE DISTRIBUTED LOCK                                               │
│      2.1. Acquire Redis lock: `lock:asset:{asset_id}`                     │
│      2.2. If lock acquisition fails:                                        │
│           • Return LOCK_ERROR (retry after delay)                          │
│                                                                              │
│   3. CHECK AVAILABILITY                                                     │
│      3.1. Query existing bookings for overlapping time:                    │
│           SELECT * FROM bookings                                            │
│           WHERE asset_id = :asset_id                                         │
│           AND status NOT IN ('CANCELLED', 'EXPIRED')                        │
│           AND (                                                           │
│               (start_time < :end_time AND end_time > :start_time)         │
│           )                                                                │
│      3.2. Calculate booked quantity for overlap                            │
│      3.3. Check capacity constraints                                        │
│      3.4. If overlap exceeds capacity:                                     │
│           • Return AVAILABILITY_ERROR                                       │
│                                                                              │
│   4. VALIDATE ASSET RULES                                                  │
│      4.1. Check asset's availability rules                                  │
│      4.2. Verify time slot within allowed times                            │
│      4.3. Check day of week restrictions                                   │
│      4.4. Validate advance booking constraints                             │
│      4.5. If any rule violated:                                            │
│           • Return VALIDATION_ERROR                                         │
│                                                                              │
│   5. CALCULATE PRICING                                                     │
│      5.1. Find applicable pricing rule                                     │
│      5.2. Calculate base price:                                            │
│           base_price = pricing_rule.calculate_price(                        │
│               quantity=quantity,                                            │
│               duration_minutes=duration                                     │
│           )                                                                 │
│      5.3. Apply quantity discounts if applicable                          │
│      5.4. Calculate service fee (percentage)                              │
│      5.5. Calculate taxes based on jurisdiction                           │
│      5.6. Generate price breakdown                                          │
│                                                                              │
│   6. CREATE BOOKING RECORD                                                  │
│      6.1. Create booking with status PENDING                               │
│      6.2. Store calculated prices                                          │
│      6.3. Save price breakdown                                            │
│                                                                              │
│   7. INITIATE PAYMENT                                                       │
│      7.1. Create payment record                                            │
│      7.2. Authorize payment with Zenopay                                   │
│      7.3. If authorization fails:                                          │
│           • Update booking status to FAILED                                 │
│           • Return PAYMENT_ERROR                                           │
│                                                                              │
│   8. SCHEDULE TIMEOUT TASK                                                 │
│      8.1. Schedule Celery task: booking.expire_pending                     │
│           • Delay: 15 minutes                                              │
│                                                                              │
│   9. SEND NOTIFICATIONS                                                     │
│      9.1. Notify renter: booking pending confirmation                      │
│      9.2. Notify owner: new booking request                                │
│                                                                              │
│   10. RELEASE LOCK                                                          │
│      10.1. Release Redis lock                                              │
│                                                                              │
│   11. RETURN SUCCESS                                                        │
│      11.1. Return booking_id                                               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Availability Checking Algorithm

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    AVAILABILITY CHECKING ALGORITHM                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   FUNCTION: check_availability(asset_id, start_time, end_time, quantity)   │
│                                                                              │
│   INPUT:                                                                     │
│   • asset_id: UUID of the asset                                             │
│   • start_time: requested start                                             │
│   • end_time: requested end                                                 │
│   • quantity: requested quantity                                            │
│                                                                              │
│   OUTPUT: (is_available, conflicts[], price_quote)                          │
│                                                                              │
│   ALGORITHM:                                                                │
│   ──────────                                                                │
│                                                                              │
│   1. GET ASSET INFO                                                        │
│      1.1. Fetch asset from cache (or DB if cache miss)                      │
│      1.2. Get capacity constraints                                          │
│      1.3. Get availability rules                                            │
│                                                                              │
│   2. VALIDATE TIME SLOT                                                    │
│      2.1. Check if start_time >= now                                       │
│      2.2. Check if duration >= min_duration                                │
│      2.3. Check if duration <= max_duration                                │
│      2.4. Check if start_time aligns with granularity                       │
│      2.5. Check if within advance booking window                            │
│      2.6. If any check fails:                                              │
│           • Return (False, [], None) with error reason                     │
│                                                                              │
│   3. CHECK SCHEDULE CONFLICTS                                               │
│      3.1. Query overlapping bookings:                                      │
│           SELECT * FROM bookings                                            │
│           WHERE asset_id = :asset_id                                         │
│           AND status IN ('PENDING', 'CONFIRMED', 'ACTIVE')                  │
│           AND start_time < :end_time                                        │
│           AND end_time > :start_time                                        │
│      3.2. For each conflict:                                                │
│           • Calculate overlap quantity                                      │
│           • Store conflict details                                          │
│                                                                              │
│   4. CALCULATE AVAILABLE CAPACITY                                           │
│      4.1. total_capacity = asset.capacity                                   │
│      4.2. booked_quantity = SUM(conflict.quantity for conflicts)           │
│      4.3. available = total_capacity - booked_quantity                     │
│                                                                              │
│   5. CHECK IF REQUEST CAN FIT                                               │
│      5.1. If quantity > available:                                         │
│           • Return (False, conflicts, None)                                 │
│                                                                              │
│   6. ADD BUFFER TIME CHECK                                                  │
│      6.1. If asset has buffer requirements:                                │
│           • Check buffer before/after other bookings                        │
│           • If request violates buffer:                                    │
│             Return (False, conflicts, None)                                 │
│                                                                              │
│   7. CALCULATE PRICE QUOTE                                                  │
│      7.1. Find applicable pricing rule                                      │
│      7.2. Calculate price as described in pricing algorithm                │
│      7.3. Return quote                                                     │
│                                                                              │
│   8. RETURN RESULT                                                          │
│      8.1. Return (True, conflicts[], price_quote)                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 Double Booking Prevention Algorithm

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                  DOUBLE BOOKING PREVENTION ALGORITHM                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   KIBOSS uses a multi-layered approach to prevent double bookings:          │
│                                                                              │
│   LAYER 1: Redis Distributed Locking                                        │
│   ──────────────────────────────────                                        │
│                                                                              │
│   When creating a booking:                                                  │
│                                                                              │
│   1. Acquire lock before any availability check                            │
│      LOCK_KEY = f"lock:asset:{asset_id}"                                   │
│      LOCK_TTL = 30 seconds                                                 │
│                                                                              │
│   2. Use Redis SET with NX and EX flags:                                    │
│      result = redis.set(LOCK_KEY, "1", nx=True, ex=30)                     │
│                                                                              │
│   3. If lock already held:                                                  │
│      • Other booking in progress                                           │
│      • Retry with exponential backoff (max 3 retries)                       │
│      • After retries exhausted: return conflict error                      │
│                                                                              │
│   LAYER 2: Database Constraints                                            │
│   ─────────────────────────────────                                        │
│                                                                              │
│   Database-level constraint on overlap detection:                            │
│                                                                              │
│   CONSTRAINT: no_overlapping_confirmed_bookings                            │
│   DEFERRABLE INITIALLY DEFERRED                                             │
│                                                                              │
│   SQL:                                                                      │
│   ALTER TABLE bookings ADD CONSTRAINT no_overlap                            │
│   CHECK (NOT EXISTS (                                                      │
│       SELECT 1 FROM bookings b2                                            │
│       WHERE b2.asset_id = bookings.asset_id                                 │
│       AND b2.status IN ('CONFIRMED', 'ACTIVE')                             │
│       AND b2.id != bookings.id                                              │
│       AND (b2.start_time < bookings.end_time                               │
│            AND b2.end_time > bookings.start_time)                           │
│   ))                                                                        │
│                                                                              │
│   LAYER 3: Optimistic Concurrency Control                                   │
│   ──────────────────────────────────────────                                │
│                                                                              │
│   For concurrent requests to same time slot:                                │
│                                                                              │
│   1. Both acquire locks (first succeeds, second waits)                      │
│   2. First proceeds, creates booking, releases lock                        │
│   3. Second proceeds, finds overlap with first's booking                   │
│   4. Second's booking fails due to capacity                                 │
│                                                                              │
│   LAYER 4: Seat-Level Locking (for rides)                                   │
│   ────────────────────────────────────────                                   │
│                                                                              │
│   For seat-based bookings:                                                  │
│                                                                              │
│   1. Lock specific seat: lock:seat:{ride_id}:{seat_number}                 │
│   2. Verify seat is available                                              │
│   3. Create seat booking                                                    │
│   4. Release lock                                                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Pricing Algorithm

### 2.1 Dynamic Pricing Calculation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     DYNAMIC PRICING ALGORITHM                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   FUNCTION: calculate_price(asset_id, quantity, duration_minutes,          │
│                           start_time, end_time)                             │
│                                                                              │
│   INPUT:                                                                     │
│   • asset_id: UUID of the asset                                             │
│   • quantity: number of units                                              │
│   • duration_minutes: rental duration                                       │
│   • start_time: rental start time                                           │
│   • end_time: rental end time                                               │
│                                                                              │
│   OUTPUT: price_breakdown                                                   │
│                                                                              │
│   ALGORITHM:                                                                │
│   ──────────                                                                │
│                                                                              │
│   1. FIND APPLICABLE PRICING RULE                                           │
│      1.1. Get all active pricing rules for asset                           │
│      1.2. Sort by priority (highest first)                                 │
│      1.3. For each rule in order:                                           │
│           • Check if rule is active                                        │
│           • Check time constraints (valid_from, valid_to)                 │
│           • Check day of week                                              │
│           • Check time of day                                              │
│           • Check duration constraints                                      │
│           • Check quantity constraints                                      │
│           • First matching rule wins                                        │
│                                                                              │
│   2. CALCULATE BASE PRICE                                                  │
│      2.1. base_price = rule.price                                          │
│      2.2. price_per_unit = base_price                                      │
│                                                                              │
│   3. APPLY QUANTITY DISCOUNTS                                               │
│      3.1. Check if rule has quantity_discounts                            │
│      3.2. For each discount:                                               │
│           if quantity >= discount.min_quantity:                             │
│               multiplier = discount.multiplier                             │
│               price_per_unit *= multiplier                                 │
│                                                                              │
│   4. CALCULATE DURATION PRICE                                               │
│      4.1. If unit is TIME_BASED (HOUR, DAY, etc.):                        │
│           units = ceil(duration / unit_conversion)                         │
│           subtotal = price_per_unit * units * quantity                      │
│      4.2. If unit is FIXED:                                               │
│           subtotal = price_per_unit * quantity                              │
│                                                                              │
│   5. APPLY TIME-BASED MODIFIERS                                             │
│      5.1. Check for weekend pricing                                        │
│      5.2. Check for peak hours                                             │
│      5.3. Check for special events                                        │
│     . Apply multipliers 5.4 if applicable                                   │
│                                                                              │
│   6. CALCULATE SERVICE FEE                                                  │
│      6.1. service_fee_rate = CONFIG.service_fee_percentage                 │
│      6.2. service_fee = subtotal * service_fee_rate                        │
│                                                                              │
│   7. CALCULATE TAXES                                                        │
│      7.1. Get tax rate from asset jurisdiction                             │
│      7.2. taxable_amount = subtotal + service_fee                         │
│      7.3. taxes = taxable_amount * tax_rate                                │
│                                                                              │
│   8. GENERATE PRICE BREAKDOWN                                               │
│      {                                                                     │
│          "base_price": 100.00,                                              │
│          "quantity_discount": 10.00,                                        │
│          "time_modifier": 0.00,                                            │
│          "subtotal": 90.00,                                                │
│          "service_fee": 9.00,                                              │
│          "taxes": 7.20,                                                   │
│          "total": 106.20,                                                  │
│          "currency": "USD",                                                 │
│          "breakdown": { ... }                                              │
│      }                                                                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Ride-Sharing Algorithm

### 3.1 Seat Availability Algorithm

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   SEAT AVAILABILITY ALGORITHM                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   FUNCTION: get_seat_availability(ride_id)                                  │
│                                                                              │
│   OUTPUT: {                                                                  │
│       "ride_id": "...",                                                     │
│       "total_seats": 4,                                                     │
│       "available_seats": 2,                                                 │
│       "seats": [                                                            │
│           {"seat_number": 1, "status": "available"},                       │
│           {"seat_number": 2, "status": "booked"},                          │
│           {"seat_number": 3, "status": "available"},                       │
│           {"seat_number": 4, "status": "booked"},                          │
│       ]                                                                     │
│   }                                                                          │
│                                                                              │
│   ALGORITHM:                                                                │
│   ──────────                                                                │
│                                                                              │
│   1. GET RIDE INFO                                                          │
│      1.1. Fetch ride from cache or DB                                       │
│      1.2. Check if ride is open for booking                                │
│                                                                              │
│   2. GET ALL SEAT BOOKINGS                                                  │
│      2.1. Query seat_bookings for ride                                     │
│      2.2. Filter by status: RESERVED, CONFIRMED, BOARDED                   │
│      2.3. Count by seat_number                                              │
│                                                                              │
│   3. BUILD SEAT MAP                                                         │
│      3.1. For seat_number in 1 to total_seats:                             │
│           • If seat in booked_seats: status = "booked"                     │
│           • Else: status = "available"                                     │
│                                                                              │
│   4. CALCULATE AVAILABLE COUNT                                              │
│      4.1. available = total_seats - confirmed_bookings                     │
│                                                                              │
│   5. CACHE RESULT                                                           │
│      5.1. Cache with 30-second TTL                                          │
│                                                                              │
│   6. RETURN RESULT                                                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Seat Booking Algorithm (Atomic)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SEAT BOOKING ALGORITHM (ATOMIC)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   FUNCTION: book_seat(ride_id, seat_number, passenger_id, payment_info)     │
│                                                                              │
│   ALGORITHM:                                                                │
│   ──────────                                                                │
│                                                                              │
│   1. VALIDATE RIDE                                                          │
│      1.1. Check ride exists and is open                                    │
│      1.2. Check ride has not departed                                       │
│      1.3. Check ride is not full                                            │
│                                                                              │
│   2. ACQUIRE SEAT LOCK                                                      │
│      2.1. LOCK_KEY = f"lock:seat:{ride_id}:{seat_number}"                  │
│      2.2. Acquire with Redis SET NX EX (30s TTL)                           │
│      2.3. If fails: return SEAT_LOCK_ERROR                                  │
│                                                                              │
│   3. ATOMIC SEAT CHECK                                                      │
│      3.1. SELECT FOR UPDATE on seat_bookings                               │
│           WHERE ride_id = :ride_id                                          │
│           AND seat_number = :seat_number                                    │
│           AND status IN ('RESERVED', 'CONFIRMED')                           │
│      3.2. If booking exists:                                                │
│           • Release lock                                                   │
│           • Return SEAT_TAKEN_ERROR                                         │
│                                                                              │
│   4. UPDATE RIDE SEAT COUNT                                                 │
│      4.1. SELECT FOR UPDATE on rides                                        │
│      4.2. If confirmed_seats >= total_seats:                               │
│           • Release lock                                                   │
│           • Return RIDE_FULL_ERROR                                         │
│      4.3. Increment confirmed_seats                                        │
│                                                                              │
│   5. CREATE SEAT BOOKING                                                   │
│      5.1. Create with status RESERVED                                       │
│      5.2. Set payment pending                                               │
│                                                                              │
│   6. PROCESS PAYMENT                                                        │
│      6.1. Authorize payment                                                 │
│      6.2. If fails:                                                         │
│           • Cancel seat booking                                             │
│           • Decrement seat count                                           │
│           • Return PAYMENT_ERROR                                           │
│                                                                              │
│   7. UPDATE TO CONFIRMED                                                    │
│      7.1. Update seat booking status to CONFIRMED                          │
│      7.2. Hold payment in escrow                                           │
│                                                                              │
│   8. RELEASE LOCK                                                           │
│                                                                              │
│   9. SEND NOTIFICATIONS                                                     │
│      9.1. Notify passenger of confirmation                                 │
│      9.2. Notify driver of new passenger                                   │
│                                                                              │
│   10. RETURN SUCCESS                                                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 No-Show Detection Algorithm

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    NO-SHOW DETECTION ALGORITHM                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   FUNCTION: process_no_shows(ride_id)                                      │
│                                                                              │
│   SCHEDULED: At departure time + no_show_cutoff_minutes                   │
│                                                                              │
│   ALGORITHM:                                                                │
│   ──────────                                                                │
│                                                                              │
│   1. GET RIDE                                                               │
│      1.1. Fetch ride with SELECT FOR UPDATE                                │
│      1.2. Check ride status = DEPARTED                                      │
│                                                                              │
│   2. GET PENDING PASSENGERS                                                 │
│      2.1. Query seat_bookings                                               │
│           WHERE ride_id = :ride_id                                          │
│           AND status IN ('RESERVED', 'CONFIRMED')                           │
│           AND checked_in_at IS NULL                                         │
│                                                                              │
│   3. PROCESS EACH NO-SHOW                                                   │
│      3.1. Mark seat_booking as NO_SHOW                                     │
│      3.2. Calculate penalty:                                               │
│           • Penalty = seat_price * no_show_penalty_rate                     │
│           • Apply to payment                                               │
│      3.3. Update passenger trust score                                      │
│                                                                              │
│   4. RELEASE UNUSED SEATS                                                   │
│      4.1. Decrement confirmed_seats                                         │
│      4.2. If standby list exists:                                           │
│           • Notify next passenger                                          │
│           • Offer seat                                                     │
│                                                                              │
│   5. UPDATE RIDE STATUS                                                     │
│      4.1. If all passengers boarded: status = IN_TRANSIT                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. State Machine Transitions

### 4.1 Booking State Transitions

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    BOOKING STATE TRANSITIONS                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   PENDING → CONFIRMED                                                       │
│   ─────────────────────                                                     │
│   Conditions:                                                               │
│   • Payment authorized                                                     │
│   • Contract accepted by both parties                                       │
│   Actions:                                                                  │
│   • Update status                                                          │
│   • Send confirmation notifications                                         │
│   • Update asset availability cache                                         │
│                                                                              │
│   PENDING → EXPIRED                                                         │
│   ──────────────────                                                       │
│   Conditions:                                                               │
│   • Payment not received within timeout (15 min)                            │
│   Actions:                                                                   │
│   • Update status                                                          │
│   • Cancel payment authorization                                           │
│   • Send expiration notification                                            │
│   • Update availability cache                                               │
│                                                                              │
│   CONFIRMED → ACTIVE                                                        │
│   ───────────────────                                                      │
│   Conditions:                                                               │
│   • Current time >= start_time                                             │
│   Actions:                                                                   │
│   • Update status                                                          │
│   • Send start notification                                                │
│   • Start monitoring for late returns                                       │
│                                                                              │
│   CONFIRMED → CANCELLED                                                     │
│   ──────────────────────                                                    │
│   Conditions:                                                               │
│   • User requested cancellation                                            │
│   • Before start_time                                                      │
│   Actions:                                                                   │
│   • Calculate cancellation fee                                             │
│   • Process refund (if applicable)                                          │
│   • Update status                                                          │
│   • Release asset availability                                              │
│   • Send cancellation notification                                          │
│                                                                              │
│   CONFIRMED → EXPIRED (No-Show)                                             │
│   ─────────────────────────────                                             │
│   Conditions:                                                               │
│   • Start_time + grace_period < now                                        │
│   • User not checked in                                                     │
│   Actions:                                                                   │
│   • Apply no-show penalty                                                  │
│   • Update status                                                          │
│   • Update trust scores                                                     │
│                                                                              │
│   ACTIVE → COMPLETED                                                        │
│   ──────────────────                                                       │
│   Conditions:                                                               │
│   • User returned asset                                                    │
│   • Current time >= end_time                                                │
│   Actions:                                                                   │
│   • Calculate late fees (if applicable)                                     │
│   • Process final payment                                                  │
│   • Release escrow to owner                                                │
│   • Enable ratings                                                         │
│   • Update status                                                          │
│                                                                              │
│   ACTIVE → CANCELLED (Early Termination)                                    │
│   ───────────────────────────────────                                       │
│   Conditions:                                                               │
│   • User returned early                                                    │
│   Actions:                                                                   │
│   • Recalculate price for actual duration                                  │
│   • Process refund or additional charge                                     │
│   • Release escrow                                                         │
│   • Update status                                                          │
│                                                                              │
│   ANY → DISPUTED                                                            │
│   ───────────────                                                           │
│   Conditions:                                                               │
│   • User raised dispute                                                    │
│   Actions:                                                                   │
│   • Freeze payment                                                         │
│   • Create dispute record                                                  │
│   • Notify all parties                                                     │
│   • Update status                                                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Overlap Detection Algorithm

### 5.1 Time Overlap Detection

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    TIME OVERLAP DETECTION                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   FUNCTION: detect_overlaps(asset_id, start_time, end_time, exclude_id)    │
│                                                                              │
│   ALGORITHM:                                                                │
│   ──────────                                                                │
│                                                                              │
│   Two time intervals [A_start, A_end) and [B_start, B_end) overlap if:    │
│                                                                              │
│   A_start < B_end AND A_end > B_start                                      │
│                                                                              │
│   SQL QUERY:                                                                │
│   ───────────                                                               │
│                                                                              │
│   SELECT * FROM bookings                                                    │
│   WHERE asset_id = :asset_id                                               │
│   AND status NOT IN ('CANCELLED', 'EXPIRED', 'COMPLETED')                  │
│   AND id != COALESCE(:exclude_id, id)                                      │
│   AND (                                                                     │
│       (start_time < :end_time AND end_time > :start_time)                  │
│   )                                                                          │
│   ORDER BY start_time                                                       │
│                                                                              │
│   EFFICIENCY:                                                               │
│   ──────────                                                                │
│                                                                              │
│   Index on:                                                                 │
│   • (asset_id, status, start_time, end_time)                                │
│   • Covers WHERE clause                                                     │
│   • Fast index range scan                                                   │
│                                                                              │
│   CACHING STRATEGY:                                                         │
│   ─────────────────                                                         │
│                                                                              │
│   • Cache availability for 1 minute                                         │
│   • Invalidate on booking changes                                           │
│   • Use for read-heavy workloads                                            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Capacity-Based Overlap

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                  CAPACITY-BASED OVERLAP CALCULATION                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   For assets with capacity > 1 (e.g., 4-seat vehicle):                     │
│                                                                              │
│   INPUT:                                                                     │
│   • Existing bookings: [                                                     │
│       {start: 10:00, end: 12:00, quantity: 2},                             │
│       {start: 11:00, end: 13:00, quantity: 1},                             │
│   ]                                                                          │
│   • New request: {start: 11:30, end: 12:30, quantity: 2}                  │
│                                                                              │
│   CALCULATION:                                                               │
│   ─────────────                                                              │
│                                                                              │
│   Overlap window: 11:30 - 12:00 (30 minutes)                                 │
│                                                                              │
│   Booking 1: 10:00-12:00 with qty 2                                         │
│   Overlap with request: 11:30-12:00                                         │
│   Contributes: 2 seats                                                      │
│                                                                              │
│   Booking 2: 11:00-13:00 with qty 1                                         │
│   Overlap with request: 11:30-12:30                                         │
│   Contributes: 1 seat                                                       │
│                                                                              │
│   Total booked in overlap: 3 seats                                           │
│   Capacity: 4 seats                                                         │
│   Request quantity: 2 seats                                                  │
│   Available: 4 - 3 = 1 seat                                                 │
│                                                                              │
│   RESULT: Request for 2 seats CANNOT be accommodated                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Cancellation Fee Algorithm

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CANCELLATION FEE ALGORITHM                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   FUNCTION: calculate_cancellation_fee(booking, cancel_time)                │
│                                                                              │
│   CANCELLATION POLICY TIER:                                                 │
│   ─────────────────────────                                                 │
│                                                                              │
│   Tier 1: More than 48 hours before start                                   │
│   Fee: 0% of subtotal                                                       │
│   Refund: 100%                                                              │
│                                                                              │
│   Tier 2: 24-48 hours before start                                           │
│   Fee: 25% of subtotal                                                      │
│   Refund: 75%                                                               │
│                                                                              │
│   Tier 3: 12-24 hours before start                                          │
│   Fee: 50% of subtotal                                                      │
│   Refund: 50%                                                               │
│                                                                              │
│   Tier 4: 2-12 hours before start                                           │
│   Fee: 75% of subtotal                                                      │
│   Refund: 25%                                                               │
│                                                                              │
│   Tier 5: Less than 2 hours before start                                    │
│   Fee: 100% of subtotal                                                     │
│   Refund: 0%                                                                │
│                                                                              │
│   Tier 6: After start time                                                  │
│   Fee: 100% + late fee                                                      │
│   Refund: 0%                                                                │
│                                                                              │
│   ALGORITHM:                                                                │
│   ──────────                                                                │
│                                                                              │
│   1. Calculate hours_until_start = start_time - cancel_time (in hours)     │
│                                                                              │
│   2. Determine tier:                                                        │
│      IF hours_until_start > 48: TIER_1                                      │
│      ELSE IF hours_until_start > 24: TIER_2                                 │
│      ELSE IF hours_until_start > 12: TIER_3                                 │
│      ELSE IF hours_until_start > 2: TIER_4                                 │
│      ELSE IF hours_until_start > 0: TIER_5                                 │
│      ELSE: TIER_6                                                           │
│                                                                              │
│   3. Calculate fees:                                                        │
│      cancellation_fee = subtotal * tier_percentage                          │
│      service_fee_refund = service_fee * refund_percentage                   │
│      taxes_refund = taxes * refund_percentage                               │
│                                                                              │
│   4. Calculate refund:                                                       │
│      refund_amount = subtotal - cancellation_fee                            │
│                     + service_fee_refund                                    │
│                     + taxes_refund                                          │
│                                                                              │
│   5. Return breakdown:                                                      │
│      {                                                                     │
│          "cancellation_fee": 25.00,                                        │
│          "service_fee_refund": 5.00,                                       │
│          "taxes_refund": 2.00,                                             │
│          "total_refund": 75.00,                                            │
│          "tier": "25% fee - 24-48 hours",                                  │
│          "hours_until_start": 36                                           │
│      }                                                                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Late Return Algorithm

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      LATE RETURN ALGORITHM                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   FUNCTION: process_late_return(booking, actual_return_time)               │
│                                                                              │
│   INPUT:                                                                     │
│   • booking: Booking object                                                 │
│   • actual_return_time: When item was actually returned                     │
│                                                                              │
│   ALGORITHM:                                                                │
│   ──────────                                                                │
│                                                                              │
│   1. CALCULATE LATE DURATION                                                │
│      1.1. grace_period = booking.grace_period_minutes                      │
│      1.2. late_minutes = (actual_return_time - end_time) - grace_period    │
│      1.3. IF late_minutes <= 0:                                             │
│           • No late fee                                                    │
│           • Return COMPLETED                                               │
│                                                                              │
│   2. CALCULATE LATE FEE                                                    │
│      2.1. late_hours = ceil(late_minutes / 60)                            │
│      2.2. fee_per_hour = booking.late_fee_per_unit                         │
│      2.3. max_fee = booking.late_fee_max                                   │
│                                                                              │
│      2.4. calculated_fee = late_hours * fee_per_hour * quantity            │
│      2.5. late_fee = min(calculated_fee, max_fee)                          │
│                                                                              │
│   3. PROCESS PAYMENT ADJUSTMENT                                             │
│      3.1. IF payment is in escrow:                                         │
│           • Deduct late_fee from escrow                                    │
│      3.2. ELSE:                                                            │
│           • Charge to card on file                                          │
│                                                                              │
│   4. UPDATE TRUST SCORE                                                     │
│      4.1. Apply penalty to renter trust score                               │
│      4.2. Record late return in trust details                              │
│                                                                              │
│   5. UPDATE BOOKING                                                         │
│      5.1. is_late = True                                                   │
│      5.2. late_minutes = late_minutes                                      │
│      5.3. late_fee_charged = late_fee                                       │
│      5.4. status = COMPLETED                                               │
│                                                                              │
│   6. SEND NOTIFICATIONS                                                     │
│      6.1. Notify renter: late fee applied                                   │
│      6.2. Notify owner: item returned, late fee details                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Summary

This document describes the core algorithms powering KIBOSS:

1. **Booking Algorithm**: Complete flow from request to confirmation
2. **Availability Checking**: Multi-factor validation with overlap detection
3. **Double Booking Prevention**: 4-layer defense (Redis locks, DB constraints, optimistic concurrency, seat locking)
4. **Dynamic Pricing**: Rule-based pricing with quantity discounts and time modifiers
5. **Ride-Sharing**: Atomic seat booking with no-show detection
6. **State Machine**: Well-defined transitions with validation
7. **Cancellation & Late Fees**: Tiered policies with clear rules

The algorithms prioritize:
- **Correctness**: State machine ensures valid transitions
- **Concurrency**: Distributed locks prevent race conditions
- **Fairness**: First-come-first-served with atomic operations
- **Performance**: Caching, indexing, and efficient queries
- **User Experience**: Clear error messages and fee breakdowns
