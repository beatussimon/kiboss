# KIBOSS - System Architecture Diagram

## Executive Summary

KIBOSS (Universal Rental & Sharing Operating System) is a local-first, production-grade rental platform built with Django/DRF and React. The architecture prioritizes correctness, security, and performance while supporting diverse rental scenarios (spaces, tools, vehicles, time-based services, seat-based ride-sharing).

---

## 1. High-Level Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           KIBOSS SYSTEM ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         CLIENT LAYER                                  │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │   │
│  │  │   React     │  │   Mobile    │  │   Admin     │  │   API       │  │   │
│  │  │   Web App   │  │   App       │  │   Dashboard │  │   Clients   │  │   │
│  │  │             │  │  (PWA/Native│  │             │  │  (curl/sdk) │  │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  │   │
│  │         │                │                │                │         │   │
│  │         └────────────────┴────────────────┴────────────────┘         │   │
│  │                                   │                                    │   │
│  │                           HTTPS/WSS (Local)                            │   │
│  └───────────────────────────────────┼────────────────────────────────────┘   │
│                                      │                                         │
│  ┌───────────────────────────────────▼────────────────────────────────────┐   │
│  │                    DJANGO REST FRAMEWORK API GATEWAY                   │   │
│  │  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌─────────────┐  │   │
│  │  │ Authentication│ │ Rate Limiting │ │ Request       │ │ Response    │  │   │
│  │  │ (JWT)        │ │ (Redis)       │ │ Validation    │ │ Serializers │  │   │
│  │  └───────────────┘ └───────────────┘ └───────────────┘ └─────────────┘  │   │
│  └───────────────────────────────────┬────────────────────────────────────┘   │
│                                      │                                         │
│  ┌───────────────────────────────────▼────────────────────────────────────┐   │
│  │                      APPLICATION SERVICES LAYER                         │   │
│  │                                                                          │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐        │   │
│  │  │  Booking    │ │  Contract   │ │   Payment   │ │  Messaging  │        │   │
│  │  │  Engine     │ │  Engine     │ │  (Zenopay)  │ │  Service    │        │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘        │   │
│  │                                                                          │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐        │   │
│  │  │   Ride      │ │  Rating &   │ │ Notification│ │   Asset      │        │   │
│  │  │  Sharing    │ │   Trust     │ │  Service    │ │  Management │        │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘        │   │
│  │                                                                          │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐        │   │
│  │  │   User      │ │   RBAC &    │ │   Audit     │ │   Reports   │        │   │
│  │  │  Management │ │   Permissions│ │   Logging   │ │   Service   │        │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘        │   │
│  └───────────────────────────────────┬────────────────────────────────────┘   │
│                                      │                                         │
│  ┌───────────────────────────────────▼────────────────────────────────────┐   │
│  │                         DOMAIN MODEL LAYER                             │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐        │   │
│  │  │   Asset     │ │  Booking    │ │  Contract   │ │   Payment   │        │   │
│  │  │  Models     │ │  Models     │ │  Models     │ │  Models     │        │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘        │   │
│  │                                                                          │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐        │   │
│  │  │   User      │ │   Ride      │ │  Messaging  │ │  Rating     │        │   │
│  │  │  Models     │ │  Models     │ │  Models     │ │  Models     │        │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘        │   │
│  │                                                                          │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐        │   │
│  │  │   Audit     │ │  Notification│ │ RBAC        │ │  Geo        │        │   │
│  │  │  Models     │ │  Models     │ │  Models     │ │  Models     │        │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘        │   │
│  └───────────────────────────────────┬────────────────────────────────────┘   │
│                                      │                                         │
│  ┌───────────────────────────────────▼────────────────────────────────────┐   │
│  │                          DATA PERSISTENCE LAYER                         │   │
│  │                                                                          │   │
│  │  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────┐  │   │
│  │  │   SQLite (Primary)  │  │   Redis (Cache &    │  │   Local Files   │  │   │
│  │  │   - Assets          │  │     Locks)          │  │   - Media       │  │   │
│  │  │   - Bookings        │  │   - Session Cache   │  │   - Contracts   │  │   │
│  │  │   - Contracts       │  │   - Rate Limits     │  │   - Logs        │  │   │
│  │  │   - Users           │  │   - Booking Locks   │  │   - Backups     │  │   │
│  │  │   - Messaging       │  │   - Celery Results  │  │                 │  │   │
│  │  └─────────────────────┘  └─────────────────────┘  └─────────────────┘  │   │
│  │                                                                          │   │
│  │                        (PostgreSQL Ready)                                │   │
│  └───────────────────────────────────┬────────────────────────────────────┘   │
│                                      │                                         │
│  ┌───────────────────────────────────▼────────────────────────────────────┐   │
│  │                      ASYNC TASK PROCESSING LAYER                      │   │
│  │                                                                          │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐     │   │
│  │  │                      CELERY WORKERS                             │     │   │
│  │  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌──────────┐ │     │   │
│  │  │  │   Booking   │ │  Contract   │ │  Payment    │ │  Notif   │ │     │   │
│  │  │  │  Tasks      │ │  Tasks      │ │  Tasks      │ │  Tasks   │ │     │   │
│  │  │  └─────────────┘ └─────────────┘ └─────────────┘ └──────────┘ │     │   │
│  │  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌──────────┐ │     │   │
│  │  │  │   Rating    │ │   Report    │ │   Cleanup   │ │  Expiry  │ │     │   │
│  │  │  │  Tasks      │ │  Tasks      │ │  Tasks      │ │  Tasks   │ │     │   │
│  │  │  └─────────────┘ └─────────────┘ └─────────────┘ └──────────┘ │     │   │
│  │  └─────────────────────────────────────────────────────────────────┘     │   │
│  │                                                                          │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐     │   │
│  │  │                   DJANGO CHANNELS (WebSocket)                   │     │   │
│  │  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌──────────┐ │     │   │
│  │  │  │  Messaging  │ │  Notifications│ │ Live       │ │  Status  │ │     │   │
│  │  │  │  Real-time  │ │  Push        │ │  Updates    │ │  Updates │ │     │   │
│  │  │  └─────────────┘ └─────────────┘ └─────────────┘ └──────────┘ │     │   │
│  │  └─────────────────────────────────────────────────────────────────┘     │   │
│  │                                                                          │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐     │   │
│  │  │                     REDIS (Message Broker)                      │     │   │
│  │  └─────────────────────────────────────────────────────────────────┘     │   │
│  │                                                                          │   │
│  └───────────────────────────────────┬────────────────────────────────────┘   │
│                                      │                                         │
│  ┌───────────────────────────────────▼────────────────────────────────────┐   │
│  │                         EXTERNAL INTEGRATIONS                          │   │
│  │                                                                          │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │   │
│  │  │  Zenopay    │  │   Email     │  │   SMS       │  │   Maps      │     │   │
│  │  │  (Mock)     │  │  (Local)    │  │  (Local)    │  │  (Local)    │     │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘     │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. System Component Architecture

### 2.1 Core Components Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          REQUEST FLOW DIAGRAM                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   CLIENT                                                                    │
│      │                                                                        │
│      ▼                                                                        │
│   ┌───────────────┐                                                         │
│   │  HTTPS Request│                                                         │
│   └───────┬───────┘                                                         │
│           │                                                                  │
│           ▼                                                                  │
│   ┌───────────────┐                                                         │
│   │  JWT Token    │ ─── Invalid? ───► 401 Unauthorized                      │
│   │  Validation   │                                                         │
│   └───────┬───────┘                                                         │
│           │                                                                  │
│           ▼                                                                  │
│   ┌───────────────┐                                                         │
│   │  Rate Limiting│ ─── Exceeded? ───► 429 Too Many Requests                 │
│   │  (Redis)     │                                                         │
│   └───────┬───────┘                                                         │
│           │                                                                  │
│           ▼                                                                  │
│   ┌───────────────┐                                                         │
│   │  View/        │                                                         │
│   │  Endpoint     │                                                         │
│   └───────┬───────┘                                                         │
│           │                                                                  │
│           ▼                                                                  │
│   ┌───────────────┐                                                         │
│   │  Permission   │ ─── Denied? ───► 403 Forbidden                          │
│   │  Check (RBAC) │                                                         │
│   └───────┬───────┘                                                         │
│           │                                                                  │
│           ▼                                                                  │
│   ┌───────────────┐                                                         │
│   │  Serializer   │ ─── Invalid? ───► 400 Bad Request                       │
│   │  Validation   │                                                         │
│   └───────┬───────┘                                                         │
│           │                                                                  │
│           ▼                                                                  │
│   ┌───────────────┐                                                         │
│   │  Service      │                                                         │
│   │  Layer        │                                                         │
│   └───────┬───────┘                                                         │
│           │                                                                  │
│           ├──► Redis Lock (if needed)                                        │
│           │         │                                                        │
│           │         ▼                                                        │
│           │   ┌───────────┐                                                  │
│           │   │  Locked?  │ ───► Retry / Abort                               │
│           │   └─────┬─────┘                                                  │
│           │         │                                                        │
│           ▼         ▼                                                        │
│   ┌───────────────┐                                                         │
│   │  Domain       │                                                         │
│   │  Operations   │                                                         │
│   └───────┬───────┘                                                         │
│           │                                                                  │
│           ▼                                                                  │
│   ┌───────────────┐                                                         │
│   │  Database     │                                                         │
│   │  Transaction  │                                                         │
│   └───────┬───────┘                                                         │
│           │                                                                  │
│           ▼                                                                  │
│   ┌───────────────┐                                                         │
│   │  Celery Task  │ ──► Async Processing                                    │
│   │  (if needed)  │                                                         │
│   └───────┬───────┘                                                         │
│           │                                                                  │
│           ▼                                                                  │
│   ┌───────────────┐                                                         │
│   │  WebSocket    │ ◄── Push Updates (Channels)                              │
│   │  (if needed)  │                                                         │
│   └───────┬───────┘                                                         │
│           │                                                                  │
│           ▼                                                                  │
│   ┌───────────────┐                                                         │
│   │  HTTP Response│                                                         │
│   │  (JSON)       │                                                         │
│   └───────────────┘                                                         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Booking Engine State Machine

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      BOOKING STATE MACHINE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                           ┌─────────────┐                                    │
│                           │   START     │                                    │
│                           └──────┬──────┘                                    │
│                                  │                                           │
│                                  ▼                                           │
│                         ┌───────────────┐                                    │
│          ┌─────────────│   PENDING     │─────────────┐                      │
│          │             │  (Awaiting     │             │                      │
│          │             │   Payment)    │             │                      │
│          │             └───────┬───────┘             │                      │
│          │                     │                      │                      │
│          │                     ▼                      │                      │
│          │             ┌───────────────┐             │                      │
│          │             │   CONFIRMED   │─────────────┼──────► EXPIRED       │
│          │             │  (Paid &      │   Timeout    │      (Celery)        │
│          │             │   Accepted)   │             │                      │
│          │             └───────┬───────┘             │                      │
│          │                     │                      │                      │
│          │                     ▼                      │                      │
│          │             ┌───────────────┐             │                      │
│          │             │    ACTIVE     │─────────────┼──────► CANCELLED     │
│          │             │  (In Progress)│   Cancel    │      (By User)       │
│          │             └───────┬───────┘             │                      │
│          │                     │                      │                      │
│          │                     ▼                      │                      │
│          │             ┌───────────────┐             │                      │
│          │             │  COMPLETED    │─────────────┼──────► DISPUTED      │
│          │             │  (Success)    │   Dispute   │      (By Party)      │
│          │             └───────┬───────┘             │                      │
│          │                     │                      │                      │
│          └─────────────────────┘                      │                      │
│                                                      │                      │
│                       ┌──────────────────────────────┘                      │
│                       │                                                     │
│                       ▼                                                     │
│                ┌──────────────┐                                              │
│                │  CANCELLED   │                                              │
│                │  (By System) │                                              │
│                └──────────────┘                                              │
│                                                                              │
│  VALID STATE TRANSITIONS:                                                   │
│  ────────────────────────                                                   │
│  PENDING    → CONFIRMED  (payment successful + contract accepted)          │
│  PENDING    → EXPIRED    (payment timeout - Celery)                          │
│  CONFIRMED  → ACTIVE     (start time reached)                               │
│  CONFIRMED  → EXPIRED    (no-show - Celery)                                 │
│  CONFIRMED  → CANCELLED  (user cancellation before start)                   │
│  ACTIVE     → COMPLETED  (end time reached + returned)                       │
│  ACTIVE     → CANCELLED  (early termination)                                │
│  ACTIVE     → DISPUTED   (issues during rental)                             │
│  COMPLETED  → DISPUTED   (post-rental disputes)                             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Contract Lifecycle

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      CONTRACT LIFECYCLE                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────┐                                                           │
│   │   DRAFT     │                                                           │
│   └──────┬──────┘                                                           │
│          │                                                                   │
│          ▼                                                                   │
│   ┌─────────────┐     ┌─────────────────┐                                    │
│   │ GENERATED   │────►│  PARTIES        │                                    │
│   │ (Snapshot)   │     │  NOTIFIED       │                                    │
│   └──────┬──────┘     └─────────────────┘                                    │
│          │                                                                   │
│          ▼                                                                   │
│   ┌─────────────────┐     ┌─────────────────┐                                │
│   │  PENDING        │────►│  OWNER          │                                │
│   │  ACCEPTANCE     │     │  ACCEPTED       │                                │
│   └─────────────────┘     └────────┬────────┘                                │
│                                    │                                         │
│                                    ▼                                         │
│                           ┌─────────────────┐                                │
│                           │  RENTER         │                                │
│                           │  ACCEPTED       │                                │
│                           └────────┬────────┘                                │
│                                    │                                         │
│                                    ▼                                         │
│                           ┌─────────────────┐                                │
│                           │  EXECUTED       │                                │
│                           │  (Immutable)    │                                │
│                           └─────────────────┘                                │
│                                    │                                         │
│                                    ▼                                         │
│                           ┌─────────────────┐                                │
│                           │  COMPLETED      │                                │
│                           │  (Signed by     │                                │
│                           │   Both)         │                                │
│                           └─────────────────┘                                │
│                                    │                                         │
│                                    ▼                                         │
│                           ┌─────────────────┐                                │
│                           │  ARCHIVED      │                                │
│                           │  (Permanent)   │                                │
│                           └─────────────────┘                                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Data Flow Architecture

### 3.1 Booking Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      BOOKING DATA FLOW                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌────────────────────────────────────────────────────────────────────┐    │
│   │                         EXTERNAL EVENTS                            │    │
│   │                                                                     │    │
│   │   [User Creates Booking] ───► [Availability Check (Redis)]        │    │
│   │                                                                     │    │
│   └─────────────────────────────┬───────────────────────────────────────┘    │
│                                 │                                            │
│                                 ▼                                            │
│   ┌────────────────────────────────────────────────────────────────────┐    │
│   │                    BOOKING REQUEST HANDLER                         │    │
│   │                                                                     │    │
│   │   1. Validate input                                                 │    │
│   │   2. Acquire Redis lock (distributed_lock:asset:{id})            │    │
│   │   3. Check availability (DB + Redis cache)                         │    │
│   │   4. Calculate pricing                                            │    │
│   │   5. Generate contract snapshot                                    │    │
│   │   6. Create PENDING booking                                        │    │
│   │   7. Release Redis lock                                            │    │
│   │   8. Schedule payment timeout (Celery)                             │    │
│   │   9. Emit booking.created event                                    │    │
│   │                                                                     │    │
│   └─────────────────────────────┬───────────────────────────────────────┘    │
│                                 │                                            │
│                                 ▼                                            │
│   ┌────────────────────────────────────────────────────────────────────┐    │
│   │                    PAYMENT PROCESSING                              │    │
│   │                                                                     │    │
│   │   ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐   │    │
│   │   │  Zenopay    │  │  Escrow     │  │  Payment Confirmation   │   │    │
│   │   │  Auth       │  │  Hold       │  │  Webhook               │   │    │
│   │   └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘   │    │
│   │          │                │                      │                 │    │
│   │          ▼                ▼                      ▼                 │    │
│   │   ┌──────────────────────────────────────────────────────────┐   │    │
│   │   │           BOOKING STATE UPDATE                            │   │    │
│   │   │   PENDING → CONFIRMED (if payment successful)             │   │    │
│   │   │   PENDING → EXPIRED (if payment timeout)                   │   │    │
│   │   └──────────────────────────────────────────────────────────┘   │    │
│   │                                                                     │    │
│   └─────────────────────────────┬───────────────────────────────────────┘    │
│                                 │                                            │
│                                 ▼                                            │
│   ┌────────────────────────────────────────────────────────────────────┐    │
│   │                    CONTRACT GENERATION                             │    │
│   │                                                                     │    │
│   │   1. Snapshot booking details                                      │    │
│   │   2. Include pricing, terms, jurisdiction                          │    │
│   │   3. Store immutable contract record                                │    │
│   │   4. Notify parties for acceptance                                  │    │
│   │   5. Update booking status                                          │    │
│   │                                                                     │    │
│   └─────────────────────────────┬───────────────────────────────────────┘    │
│                                 │                                            │
│                                 ▼                                            │
│   ┌────────────────────────────────────────────────────────────────────┐    │
│   │                    BOOKING EXECUTION                                 │    │
│   │                                                                     │    │
│   │   AT START TIME:                                                    │    │
│   │   ┌─────────────────────────────────────────────────────────────┐   │    │
│   │   │ 1. Celery triggers: ACTIVE_CHECK task                       │   │    │
│   │   │ 2. Update booking to ACTIVE                                 │   │    │
│   │   │ 3. Notify parties                                            │   │    │
│   │   │ 4. Start monitoring for late returns                         │   │    │
│   │   └─────────────────────────────────────────────────────────────┘   │    │
│   │                                                                     │    │
│   │   AT END TIME:                                                     │    │
│   │   ┌─────────────────────────────────────────────────────────────┐   │    │
│   │   │ 1. Celery triggers: COMPLETION_CHECK task                   │   │    │
│   │   │ 2. Verify return/completion                                 │   │    │
│   │   │ 3. Process late fees if applicable                          │   │    │
│   │   │ 4. Release escrow to owner                                   │   │    │
│   │   │ 5. Enable ratings                                           │   │    │
│   │   │ 6. Update booking to COMPLETED                              │   │    │
│   │   └─────────────────────────────────────────────────────────────┘   │    │
│   │                                                                     │    │
│   └────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Ride-Sharing Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    RIDE-SHARING DATA FLOW                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌────────────────────────────────────────────────────────────────────┐    │
│   │                    RIDE DEFINITION                                  │    │
│   │                                                                     │    │
│   │   ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐   │    │
│   │   │ Route       │  │ Schedule    │  │  Vehicle/Capacity       │   │    │
│   │   │ Definition  │  │ (Recurring) │  │  Definition             │   │    │
│   │   └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘   │    │
│   │          │                │                      │                 │    │
│   │          └────────────────┴──────────────────────┘                 │    │
│   │                             │                                        │    │
│   │                             ▼                                        │    │
│   │              ┌─────────────────────────────┐                         │    │
│   │              │     RIDE SCHEDULE INSTANCE  │                         │    │
│   │              │  (Generated from recurring) │                         │    │
│   │              └─────────────────────────────┘                         │    │
│   │                                                                     │    │
│   └─────────────────────────────┬───────────────────────────────────────┘    │
│                                 │                                            │
│                                 ▼                                            │
│   ┌────────────────────────────────────────────────────────────────────┐    │
│   │                    SEAT BOOKING PROCESS                            │    │
│   │                                                                     │    │
│   │   1. User selects ride and seats                                    │    │
│   │   2. System checks seat availability (atomic operation)           │    │
│   │   3. User proceeds to payment                                       │    │
│   │   4. Seat is temporarily held (Redis lock)                         │    │
│   │   5. Payment processing                                             │    │
│   │   6. Seat confirmed (DB update)                                    │    │
│   │   7. Contract generated per passenger                               │    │
│   │   8. Notifications sent                                            │    │
│   │                                                                     │    │
│   └─────────────────────────────┬───────────────────────────────────────┘    │
│                                 │                                            │
│                                 ▼                                            │
│   ┌────────────────────────────────────────────────────────────────────┐    │
│   │                    RIDE EXECUTION                                   │    │
│   │                                                                     │    │
│   │   AT DEPARTURE TIME:                                                │    │
│   │   ┌─────────────────────────────────────────────────────────────┐   │    │
│   │   │ • Driver checks in                                          │   │    │
│   │   │ • System verifies confirmed passengers                      │   │    │
│   │   │ • Late passengers marked as no-show                         │   │    │
│   │   │ • Seats released for standby if applicable                 │   │    │
│   │   └─────────────────────────────────────────────────────────────┘   │    │
│   │                                                                     │    │
│   │   DURING RIDE:                                                      │    │
│   │   ┌─────────────────────────────────────────────────────────────┐   │    │
│   │   │ • GPS tracking (if enabled)                                 │   │    │
│   │   │ • Real-time status updates via WebSocket                    │   │    │
│   │   │ • Passenger/driver messaging                                │   │    │
│   │   │ • Emergency contacts                                        │   │    │
│   │   └─────────────────────────────────────────────────────────────┘   │    │
│   │                                                                     │    │
│   │   AT COMPLETION:                                                    │    │
│   │   ┌─────────────────────────────────────────────────────────────┐   │    │
│   │   │ • Driver marks complete                                     │   │    │
│   │   │ • Ratings enabled for both parties                          │   │    │
│   │   │ • Escrow released to driver                                 │   │    │
│   │   │ • Dispute window opens                                       │   │    │
│   │   └─────────────────────────────────────────────────────────────┘   │    │
│   │                                                                     │    │
│   └────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Redis Architecture

### 4.1 Redis Data Structures

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      REDIS DATA STRUCTURES                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   KEY PATTERN                           TYPE        DESCRIPTION             │
│   ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│   CACHE LAYER:                                                                │
│   ─────────────                                                                │
│   cache:asset:{id}                   Hash         Asset details (hot path)  │
│   cache:asset:list:{filters}         Set          Asset list (page)         │
│   cache:user:{id}                    Hash         User profile (hot path)   │
│   cache:booking:{id}                 Hash         Booking details            │
│   cache:ride:{id}                    Hash         Ride schedule details      │
│                                                                              │
│   LOCKING:                                                                   │
│   ────────                                                                   │
│   lock:asset:{id}                    String       Asset availability lock    │
│   lock:booking:{id}                  String       Booking operation lock     │
│   lock:seat:{ride_id}:{seat_num}    String       Seat booking lock          │
│   lock:contract:{id}                 String       Contract operation lock    │
│   lock:payment:{booking_id}         String       Payment processing lock     │
│                                                                              │
│   RATE LIMITING:                                                             │
│   ───────────────                                                             │
│   ratelimit:user:{user_id}:{action} String       Rate limit counter         │
│   ratelimit:ip:{ip}:{action}         String       IP-based rate limit       │
│                                                                              │
│   SESSIONS & TOKENS:                                                         │
│   ──────────────────                                                         │
│   session:{session_id}              Hash         Session data               │
│   token:blacklist:{jti}             String       JWT blacklist (logout)     │
│   token:refresh:{user_id}           String       Refresh token storage      │
│                                                                              │
│   MESSAGING (Pub/Sub):                                                        │
│   ─────────────────────                                                       │
│   channel:chat:{thread_id}          Channel      WebSocket chat channel      │
│   channel:notify:{user_id}          Channel      User notification channel   │
│   channel:booking:{booking_id}     Channel      Booking updates channel     │
│                                                                              │
│   CELERY RESULTS:                                                            │
│   ───────────────                                                             │
│   celery:result:{task_id}           String       Task execution result       │
│   celery:status:{task_id}           String       Task status                │
│                                                                              │
│   BOOKING TIMELINE:                                                          │
│   ─────────────────                                                           │
│   booking:timeline:{booking_id}    List         Timeline events (audit)      │
│                                                                              │
│   RIDE SEAT INVENTORY:                                                        │
│   ──────────────────────                                                      │
│   ride:{ride_id}:available_seats   Set          Available seat numbers      │
│   ride:{ride_id}:booked_seats      Set          Booked seat numbers         │
│   ride:{ride_id}:seat:{seat_num}  Hash         Seat booking details         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Redis Locking Strategy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      REDIS LOCKING STRATEGY                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   LOCK ACQUISITION FLOW:                                                     │
│   ───────────────────────                                                    │
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │                     ATTEMPT LOCK                                    │   │
│   │                                                                      │   │
│   │   result = redis.set(                                               │   │
│   │       lock_key,                                                      │   │
│   │       lock_value,                                                   │   │
│   │       nx=True,          # Only set if not exists                    │   │
│   │      ex=30             # Expire after 30 seconds                    │   │
│   │   )                                                                  │   │
│   │                                                                      │   │
│   │   if result:                                                         │   │
│   │       # Lock acquired                                                │   │
│   │       try:                                                           │   │
│   │           # Critical operation                                      │   │
│   │       finally:                                                      │   │
│   │           redis.delete(lock_key)                                    │   │
│   │   else:                                                              │   │
│   │       # Lock not acquired - handle conflict                         │   │
│   │                                                                      │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   LOCK VALUE (for deadlock detection):                                      │
│   ───────────────────────────────────                                        │
│                                                                              │
│   lock_value = f"{process_id}:{thread_id}:{timestamp}"                      │
│                                                                              │
│   LOCK HIERARCHY (to prevent deadlocks):                                     │
│   ────────────────────────────────                                           │
│                                                                              │
│   MUST acquire in this order:                                                │
│   1. asset:availability lock                                                 │
│   2. seat:booking lock (for rides)                                          │
│   3. payment processing lock                                                 │
│   4. contract generation lock                                                │
│                                                                              │
│   NEVER acquire in reverse order                                             │
│                                                                              │
│   LOCK TIMEOUT & RENEWAL:                                                    │
│   ──────────────────────                                                     │
│                                                                              │
│   • Default timeout: 30 seconds                                             │
│   • Operation timeout: 25 seconds (warning threshold)                       │
│   • Renewal: If operation > 20 seconds, attempt renewal                     │
│   • Heartbeat: Every 10 seconds during long operations                      │
│                                                                              │
│   FALLBACK STRATEGY (Redis unavailable):                                    │
│   ──────────────────────────────────                                          │
│                                                                              │
│   1. Log warning to audit                                                   │
│   2. Use database row-level locking (SELECT FOR UPDATE)                    │
│   3. Process continues with degraded performance                           │
│   4. Alert administrators                                                   │
│   5. Log incident for post-mortem                                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Celery Task Architecture

### 5.1 Celery Task Categories

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      CELERY TASK ARCHITECTURE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │                    BOOKING TASKS                                     │   │
│   │                                                                      │   │
│   │   booking.expire_pending                                             │   │
│   │       • Triggered: 15 minutes after PENDING state                   │   │
│   │       • Action: Check payment status, move to EXPIRED if unpaid    │   │
│   │       • Retry: 3 times with exponential backoff                     │   │
│   │                                                                      │   │
│   │   booking.check_active                                               │   │
│   │       • Triggered: At booking start time                            │   │
│   │       • Action: Update to ACTIVE, send notifications                │   │
│   │       • Retry: 2 times                                               │   │
│   │                                                                      │   │
│   │   booking.check_completion                                          │   │
│   │       • Triggered: At booking end time                              │   │
│   │       • Action: Verify completion, process late fees, release escrow│   │
│   │       • Retry: 3 times                                               │   │
│   │                                                                      │   │
│   │   booking.process_no_show                                           │   │
│   │       • Triggered: 15 minutes after start time if not active       │   │
│   │       • Action: Mark as no-show, apply penalties, cancel           │   │
│   │       • Retry: 1 time                                                │   │
│   │                                                                      │   │
│   │   booking.process_late_return                                       │   │
│   │       • Triggered: After booking end time if not completed         │   │
│   │       • Action: Calculate late fees, update contract, notify       │   │
│   │       • Retry: 5 times (every hour)                                 │   │
│   │                                                                      │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │                    CONTRACT TASKS                                    │   │
│   │                                                                      │   │
│   │   contract.remind_accept                                            │   │
│   │       • Triggered: 1 hour after generation if not accepted         │   │
│   │       • Action: Send reminder notification                          │   │
│   │       • Retry: 2 times (every 2 hours)                              │   │
│   │                                                                      │   │
│   │   contract.archive_old                                              │   │
│   │       • Triggered: Daily at 2 AM                                    │   │
│   │       • Action: Archive contracts older than 1 year                │   │
│   │       • Retry: 1 time                                                │   │
│   │                                                                      │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │                    PAYMENT TASKS                                     │   │
│   │                                                                      │   │
│   │   payment.escrow_expire                                             │   │
│   │       • Triggered: Contractually defined escrow period end         │   │
│   │       • Action: Release to owner or extend dispute window           │   │
│   │       • Retry: 3 times                                               │   │
│   │                                                                      │   │
│   │   payment.process_refund                                            │   │
│   │       • Triggered: After cancellation or dispute resolution         │   │
│   │       • Action: Process refund to renter, apply penalties          │   │
│   │       • Retry: 5 times with notification on failure                 │   │
│   │                                                                      │   │
│   │   payment.zenopay_reconcile                                          │   │
│   │       • Triggered: Hourly                                           │   │
│   │       • Action: Reconcile with Zenopay records                      │   │
│   │       • Retry: 2 times                                               │   │
│   │                                                                      │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │                    NOTIFICATION TASKS                               │   │
│   │                                                                      │   │
│   │   notification.send_batch                                            │   │
│   │       • Triggered: Queued by application                             │   │
│   │       • Action: Send notifications in batch (rate limited)          │   │
│   │       • Retry: 3 times                                               │   │
│   │                                                                      │   │
│   │   notification.cleanup_old                                           │   │
│   │       • Triggered: Daily at 3 AM                                    │   │
│   │       • Action: Delete notifications older than 90 days            │   │
│   │       • Retry: 1 time                                                │   │
│   │                                                                      │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │                    RATING TASKS                                       │   │
│   │                                                                      │   │
│   │   rating.enable_mutual                                              │   │
│   │       • Triggered: After COMPLETED state                            │   │
│   │       • Action: Enable ratings, start 7-day window                  │   │
│   │       • Retry: 1 time                                                │   │
│   │                                                                      │   │
│   │   rating.calculate_trust                                             │   │
│   │       • Triggered: After new rating                                  │   │
│   │       • Action: Recalculate user trust score                        │   │
│   │       • Retry: 1 time                                                │   │
│   │                                                                      │   │
│   │   rating.archive_old                                                │   │
│   │       • Triggered: Monthly                                          │   │
│   │       • Action: Archive ratings older than 2 years                  │   │
│   │       • Retry: 1 time                                                │   │
│   │                                                                      │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │                    RIDE TASKS                                          │   │
│   │                                                                      │   │
│   │   ride.generate_schedules                                           │   │
│   │       • Triggered: Daily at midnight                                 │   │
│   │       • Action: Generate schedule instances for next 30 days        │   │
│   │       • Retry: 2 times                                               │   │
│   │                                                                      │   │
│   │   ride.remind_passengers                                            │   │
│   │       • Triggered: 1 hour before departure                           │   │
│   │       • Action: Send reminder with details                          │   │
│   │       • Retry: 1 time                                                │   │
│   │                                                                      │   │
│   │   ride.process_no_show                                              │   │
│   │       • Triggered: At departure time                                │   │
│   │       • Action: Mark no-shows, release seats, apply penalties      │   │
│   │       • Retry: 1 time                                                │   │
│   │                                                                      │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │                    MAINTENANCE TASKS                                  │   │
│   │                                                                      │   │
│   │   maintenance.cleanup_sessions                                       │   │
│   │       • Triggered: Hourly                                            │   │
│   │       • Action: Remove expired sessions, clean up tokens             │   │
│   │                                                                      │   │
│   │   maintenance.cache_warm                                             │   │
│   │       • Triggered: Every 5 minutes                                   │   │
│   │       • Action: Warm cache for hot paths                            │   │
│   │                                                                      │   │
│   │   maintenance.log_rotation                                           │   │
│   │       • Triggered: Daily at midnight                                 │   │
│   │       • Action: Rotate logs, archive old logs                      │   │
│   │                                                                      │   │
│   │   maintenance.database_vacuum                                        │   │
│   │       • Triggered: Daily at 4 AM                                     │   │
│   │       • Action: Vacuum SQLite database                              │   │
│   │                                                                      │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Security Architecture

### 6.1 Security Layers

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      SECURITY ARCHITECTURE LAYERS                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │                    TRANSPORT SECURITY                                  │   │
│   │                                                                      │   │
│   │   • HTTPS only (TLS 1.3)                                            │   │
│   │   • Certificate validation                                           │   │
│   │   • Secure cookies (HttpOnly, SameSite)                              │   │
│   │   • CORS configuration                                               │   │
│   │                                                                      │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│   ┌────────────────────────────────▼──────────────────────────────────────┐   │
│   │                    AUTHENTICATION LAYER                               │   │
│   │                                                                      │   │
│   │   ┌───────────────────────────────────────────────────────────────┐  │   │
│   │   │                    JWT TOKEN STRUCTURE                        │  │   │
│   │   │                                                              │  │   │
│   │   │   Header:                                                    │  │   │
│   │   │   {                                                          │  │   │
│   │   │     "alg": "RS256",                                          │  │   │
│   │   │     "typ": "JWT",                                             │  │   │
│   │   │     "kid": "key-1"  // Key ID for rotation                   │  │   │
│   │   │   }                                                          │  │   │
│   │   │                                                              │  │   │
│   │   │   Payload:                                                    │  │   │
│   │   │   {                                                          │  │   │
│   │   │     "sub": "user_id",                                        │  │   │
│   │   │     "email": "user@example.com",                             │  │   │
│   │   │     "role": "user|admin|...",                                │  │   │
│   │   │     "permissions": ["read", "write", "delete"],             │  │   │
│   │   │     "jti": "unique_token_id",  // For revocation             │  │   │
│   │   │     "iat": timestamp,                                        │  │   │
│   │   │     "exp": timestamp,                                        │  │   │
│   │   │     "refresh_id": "..."  // Refresh token reference          │  │   │
│   │   │   }                                                          │  │   │
│   │   │                                                              │  │   │
│   │   │   Signature: RS256 with RSA key pair                         │  │   │
│   │   │                                                              │  │   │
│   │   └───────────────────────────────────────────────────────────────┘  │   │
│   │                                                                      │   │
│   │   Token Lifetimes:                                                   │   │
│   │   • Access token: 15 minutes                                        │   │
│   │   • Refresh token: 7 days (rotating)                                 │   │
│   │   • Confirmation token: 24 hours                                    │   │
│   │                                                                      │   │
│   │   Token Rotation:                                                    │   │
│   │   • Access token refreshed via refresh token                        │   │
│   │   • Old refresh tokens blacklisted on use                          │   │
│   │   • Maximum 5 concurrent sessions per user                         │   │
│   │                                                                      │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│   ┌────────────────────────────────▼──────────────────────────────────────┐   │
│   │                    AUTHORIZATION LAYER (RBAC)                         │   │
│   │                                                                      │   │
│   │   ┌───────────────────────────────────────────────────────────────┐  │   │
│   │   │                    PERMISSION CHECKS                         │  │   │
│   │   │                                                              │  │   │
│   │   │   View Level:                                                │  │   │
│   │   │   • @permission_required([...]) decorators                 │  │   │
│   │   │   • IsAuthenticated + Role check                           │  │   │
│   │   │                                                              │  │   │
│   │   │   Object Level:                                              │  │   │
│   │   │   • HasObjectPermission() method                            │  │   │
│   │   │   • Owner check                                              │  │   │
│   │   │   • Shared access check                                      │  │   │
│   │   │                                                              │  │   │
│   │   │   Field Level:                                               │  │   │
│   │   │   • Serializer field permissions                            │  │   │
│   │   │   • Write vs Read fields                                     │  │   │
│   │   │                                                              │  │   │
│   │   └───────────────────────────────────────────────────────────────┘  │   │
│   │                                                                      │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│   ┌────────────────────────────────▼──────────────────────────────────────┐   │
│   │                    INPUT VALIDATION LAYER                            │   │
│   │                                                                      │   │
│   │   • Django REST Framework serializers (validation)                 │   │
│   │   • Django forms (if applicable)                                    │   │
│   │   • Custom validators (regex, business rules)                      │   │
│   │   • File upload validation (type, size, content)                   │   │
│   │   • SQL injection prevention (ORM abstraction)                     │   │
│   │   • XSS prevention (auto-escaping in templates)                    │   │
│   │   • CSRF protection (Django middleware)                           │   │
│   │                                                                      │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│   ┌────────────────────────────────▼──────────────────────────────────────┐   │
│   │                    RATE LIMITING LAYER                               │   │
│   │                                                                      │   │
│   │   Endpoint-based limits (Redis):                                    │   │
│   │   • Authentication: 5 attempts/minute, 100/day                      │   │
│   │   • General API: 1000 requests/hour, 10000/day                     │   │
│   │   • Booking creation: 10/hour, 50/day                             │   │
│   │   • Messaging: 100/hour, 500/day                                    │   │
│   │   • Upload: 50/hour, 200/day                                       │   │
│   │                                                                      │   │
│   │   IP-based limits:                                                  │   │
│   │   • Global: 5000 requests/hour                                     │   │
│   │   • Burst protection: 100 requests/minute                         │   │
│   │                                                                      │   │
│   │   Response on limit:                                                 │   │
│   │   • 429 Too Many Requests                                           │   │
│   │   • Retry-After header                                              │   │
│   │   • Progressive cooldown                                            │   │
│   │                                                                      │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│   ┌────────────────────────────────▼──────────────────────────────────────┐   │
│   │                    AUDIT & LOGGING LAYER                             │   │
│   │                                                                      │   │
│   │   All security-relevant events:                                     │   │
│   │   • Authentication (success/failure, location)                     │   │
│   │   • Authorization failures                                           │   │
│   │   • Data access (sensitive data)                                    │   │
│   │   • Configuration changes                                           │   │
│   │   • Admin actions (with justification)                              │   │
│   │   • Payment operations                                               │   │
│   │   • Contract modifications                                          │   │
│   │                                                                      │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Database Schema Overview

### 7.1 Core Entities

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      CORE DATABASE ENTITIES                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────────┐                                                       │
│   │     User        │                                                       │
│   ├─────────────────┤                                                       │
│   │ id (PK)         │                                                       │
│   │ email (UQ)      │                                                       │
│   │ password_hash   │                                                       │
│   │ role            │                                                       │
│   │ is_verified     │                                                       │
│   │ trust_score     │                                                       │
│   │ created_at      │                                                       │
│   │ updated_at      │                                                       │
│   └────────┬────────┘                                                       │
│            │                                                                │
│   ┌────────┴────────┐                                                       │
│   │ ┌─────────────┐ │                                                       │
│   │ │   Profile   │ │                                                       │
│   │ ├─────────────┤ │                                                       │
│   │ │ user_id (FK)│ │                                                       │
│   │ │ first_name  │ │                                                       │
│   │ │ last_name   │ │                                                       │
│   │ │ phone       │ │                                                       │
│   │ │ avatar      │ │                                                       │
│   │ │ bio         │ │                                                       │
│   │ └─────────────┘ │                                                       │
│   └─────────────────┘                                                       │
│                                                                              │
│   ┌─────────────────┐                                                       │
│   │     Asset       │                                                       │
│   ├─────────────────┤                                                       │
│   │ id (PK)         │                                                       │
│   │ owner_id (FK)   │                                                       │
│   │ asset_type      │ (ROOM, TOOL, VEHICLE, SEAT_SERVICE, TIME_SERVICE)    │
│   │ name            │                                                       │
│   │ description     │                                                       │
│   │ jurisdiction    │                                                       │
│   │ verification    │                                                       │
│   │ is_active       │                                                       │
│   │ created_at      │                                                       │
│   │ updated_at      │                                                       │
│   └────────┬────────┘                                                       │
│            │                                                                │
│   ┌────────┴────────┐                                                       │
│   │ ┌─────────────┐ │                                                       │
│   │ │ AssetPricing │ │                                                      │
│   │ ├─────────────┤ │                                                       │
│   │ │ asset_id (FK)│ │                                                      │
│   │ │ unit_type   │ │ (HOUR, DAY, WEEK, MILE, SEAT, FIXED)                 │
│   │ │ price       │ │                                                       │
│   │ │ min_quantity│ │                                                       │
│   │ │ max_quantity│ │                                                       │
│   │ │ rules       │ │ (JSON - discount rules, etc.)                        │
│   │ └─────────────┘ │                                                       │
│   └─────────────────┘                                                       │
│                                                                              │
│   ┌─────────────────┐                                                       │
│   │    Booking      │                                                       │
│   ├─────────────────┤                                                       │
│   │ id (PK)         │                                                       │
│   │ asset_id (FK)   │                                                       │
│   │ renter_id (FK)  │                                                       │
│   │ status          │ (PENDING, CONFIRMED, ACTIVE, COMPLETED, CANCELLED,  │
│   │                 │  EXPIRED, DISPUTED)                                   │
│   │ start_time      │                                                       │
│   │ end_time        │                                                       │
│   │ quantity        │                                                       │
│   │ total_price     │                                                       │
│   │ contract_id (FK)│                                                      │
│   │ payment_status  │                                                       │
│   │ created_at      │                                                       │
│   │ updated_at      │                                                       │
│   └────────┬────────┘                                                       │
│            │                                                                │
│   ┌────────┴────────┐                                                       │
│   │ ┌─────────────┐ │                                                       │
│   │ │  Contract   │ │                                                       │
│   │ ├─────────────┤ │                                                       │
│   │ │ id (PK)     │ │                                                       │
│   │ │ booking_id  │ │ (FK)                                                  │
│   │ │ version     │ │                                                       │
│   │ │ snapshot    │ │ (JSON - immutable contract terms)                   │
│   │ │ status      │ │ (PENDING, ACCEPTED, EXECUTED, COMPLETED, ARCHIVED)  │
│   │ │ owner_sig   │ │                                                       │
│   │ │ renter_sig  │ │                                                       │
│   │ │ accepted_at │ │                                                       │
│   │ │ created_at   │ │                                                       │
│   │ └─────────────┘ │                                                       │
│   └─────────────────┘                                                       │
│                                                                              │
│   ┌─────────────────┐                                                       │
│   │   Payment       │                                                       │
│   ├─────────────────┤                                                       │
│   │ id (PK)         │                                                       │
│   │ booking_id (FK) │                                                       │
│   │ amount          │                                                       │
│   │ status          │ (AUTHORIZED, ESCROW, RELEASED, REFUNDED, FAILED)     │
│   │ zenopay_ref     │                                                       │
│   │ created_at      │                                                       │
│   │ updated_at      │                                                       │
│   └─────────────────┘                                                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. API Gateway Architecture

### 8.1 API Endpoint Organization

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      API ENDPOINT ORGANIZATION                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   API VERSION: v1                                                           │
│   BASE PATH: /api/v1/                                                       │
│   FORMAT: JSON                                                              │
│   AUTHENTICATION: Bearer JWT                                                │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                     AUTHENTICATION (/auth/)                          │  │
│   │                                                                      │  │
│   │   POST   /auth/register/              # User registration          │  │
│   │   POST   /auth/login/                 # JWT token pair              │  │
│   │   POST   /auth/logout/                # Blacklist tokens            │  │
│   │   POST   /auth/refresh/               # Refresh access token        │  │
│   │   POST   /auth/password/reset/       # Request password reset       │  │
│   │   POST   /auth/password/confirm/     # Confirm password reset       │  │
│   │   POST   /auth/email/verify/         # Request email verification    │  │
│   │   GET    /auth/me/                   # Current user profile         │  │
│   │   PUT    /auth/me/                   # Update profile               │  │
│   │   PUT    /auth/password/             # Change password              │  │
│   │                                                                      │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                        ASSETS (/assets/)                            │  │
│   │                                                                      │  │
│   │   GET    /assets/                  # List/filter assets             │  │
│   │   POST   /assets/                  # Create new asset                │  │
│   │   GET    /assets/{id}/            # Asset details                   │  │
│   │   PUT    /assets/{id}/            # Update asset                    │  │
│   │   DELETE /assets/{id}/            # Deactivate asset                 │  │
│   │   GET    /assets/{id}/pricing/    # Get pricing rules                │  │
│   │   PUT    /assets/{id}/pricing/   # Update pricing rules             │  │
│   │   GET    /assets/{id}/calendar/  # Get availability calendar        │  │
│   │   PUT    /assets/{id}/availability/# Update availability rules     │  │
│   │   POST   /assets/{id}/verify/     # Request verification             │  │
│   │   POST   /assets/{id}/photos/    # Upload photos                    │  │
│   │   DELETE /assets/{id}/photos/{photo_id}/ # Delete photo             │  │
│   │                                                                      │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                      BOOKINGS (/bookings/)                          │  │
│   │                                                                      │  │
│   │   GET    /bookings/                 # List user's bookings          │  │
│   │   POST   /bookings/                 # Create new booking            │  │
│   │   GET    /bookings/{id}/           # Booking details                │  │
│   │   PUT    /bookings/{id}/           # Update booking (if allowed)    │  │
│   │   POST   /bookings/{id}/cancel/    # Cancel booking                 │  │
│   │   POST   /bookings/{id}/confirm/   # Confirm (owner)                 │  │
│   │   POST   /bookings/{id}/start/     # Start booking (ACTIVE)         │  │
│   │   POST   /bookings/{id}/complete/  # Complete booking                │  │
│   │   POST   /bookings/{id}/dispute/   # Raise dispute                  │  │
│   │   GET    /bookings/{id}/contract/ # Get contract                    │  │
│   │   POST   /bookings/{id}/contract/accept/ # Accept contract          │  │
│   │   GET    /bookings/{id}/timeline/ # Get booking timeline            │  │
│   │                                                                      │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                        RIDES (/rides/)                              │  │
│   │                                                                      │  │
│   │   GET    /rides/                   # List available rides          │  │
│   │   POST   /rides/                   # Create ride (driver)           │  │
│   │   GET    /rides/{id}/             # Ride details                    │  │
│   │   PUT    /rides/{id}/             # Update ride                     │  │
│   │   DELETE /rides/{id}/             # Cancel ride                     │  │
│   │   GET    /rides/{id}/seats/       # Get seat availability           │  │
│   │   POST   /rides/{id}/seats/book/  # Book seat(s)                    │  │
│   │   POST   /rides/{id}/seats/{seat}/cancel/ # Cancel seat booking    │  │
│   │   POST   /rides/{id}/checkin/     # Driver check-in                 │  │
│   │   POST   /rides/{id}/complete/    # Complete ride                   │  │
│   │   GET    /rides/{id}/passengers/  # List passengers                 │  │
│   │   POST   /rides/schedules/generate/ # Generate recurring schedules │  │
│   │                                                                      │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                      CONTRACTS (/contracts/)                        │  │
│   │                                                                      │  │
│   │   GET    /contracts/                # List contracts (filtered)      │  │
│   │   GET    /contracts/{id}/          # Contract details                │  │
│   │   GET    /contracts/{id}/history/ # Contract version history        │  │
│   │   POST   /contracts/{id}/accept/ # Accept contract                  │  │
│   │   POST   /contracts/{id}/download/ # Download PDF                  │  │
│   │   GET    /contracts/{id}/status/   # Get current status             │  │
│   │                                                                      │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                      PAYMENTS (/payments/)                          │  │
│   │                                                                      │  │
│   │   GET    /payments/               # List payments                   │  │
│   │   GET    /payments/{id}/         # Payment details                  │  │
│   │   POST   /payments/{id}/authorize/ # Authorize payment (Zenopay)   │  │
│   │   POST   /payments/{id}/capture/  # Capture authorized payment     │  │
│   │   POST   /payments/{id}/refund/   # Request refund                 │  │
│   │   POST   /payments/{id}/dispute/  # Raise payment dispute          │  │
│   │   GET    /payments/escrow/status/ # Get escrow status              │  │
│   │   POST   /payments/zenopay/webhook/ # Zenopay webhook endpoint      │  │
│   │                                                                      │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                     MESSAGING (/messages/)                           │  │
│   │                                                                      │  │
│   │   GET    /threads/               # List conversation threads        │  │
│   │   POST   /threads/               # Create new thread                 │  │
│   │   GET    /threads/{id}/         # Thread details + messages         │  │
│   │   POST   /threads/{id}/message/ # Send message                      │  │
│   │   GET    /threads/{id}/messages/# Get messages (paginated)         │  │
│   │   POST   /threads/{id}/close/   # Close thread                      │  │
│   │   POST   /threads/{id}/report/  # Report abuse                      │  │
│   │   POST   /direct/               # Send DM                           │  │
│   │   GET    /direct/conversations/ # List DM conversations             │  │
│   │                                                                      │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                     RATINGS (/ratings/)                              │  │
│   │                                                                      │  │
│   │   GET    /ratings/               # List ratings (filtered)          │  │
│   │   GET    /ratings/{id}/         # Rating details                    │  │
│   │   POST   /ratings/              # Submit rating (after completion) │  │
│   │   PUT    /ratings/{id}/         # Update rating (within window)     │  │
│   │   GET    /users/{id}/ratings/   # Get user's ratings                │  │
│   │   GET    /assets/{id}/ratings/  # Get asset ratings                 │  │
│   │   GET    /users/{id}/trust/     # Get user's trust score            │  │
│   │   POST   /ratings/{id}/report/  # Report rating                     │  │
│   │   POST   /ratings/{id}/appeal/  # Appeal moderation decision        │  │
│   │                                                                      │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                   NOTIFICATIONS (/notifications/)                   │  │
│   │                                                                      │  │
│   │   GET    /notifications/          # List notifications              │  │
│   │   GET    /notifications/{id}/     # Notification details            │  │
│   │   PUT    /notifications/{id}/read/ # Mark as read                   │  │
│   │   PUT    /notifications/read-all/ # Mark all as read               │  │
│   │   GET    /notifications/settings/ # Get notification settings       │  │
│   │   PUT    /notifications/settings/ # Update settings                 │  │
│   │                                                                      │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                        SOCIAL (/social/)                            │  │
│   │                                                                      │  │
│   │   POST   /likes/                  # Like entity                      │  │
│   │   DELETE /likes/{id}/            # Unlike                          │  │
│   │   GET    /likes/{entity_type}/{entity_id}/ # Get likes count       │  │
│   │   POST   /follows/                 # Follow user                     │  │
│   │   DELETE /follows/{id}/           # Unfollow                        │  │
│   │   GET    /follows/followers/      # Get followers                   │  │
│   │   GET    /follows/following/      # Get following                   │  │
│   │   GET    /follows/{user_id}/is_following/ # Check follow status     │  │
│   │                                                                      │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                      ADMIN (/admin/)                                 │  │
│   │                                                                      │  │
│   │   GET    /admin/users/             # List users                      │  │
│   │   PUT    /admin/users/{id}/       # Update user                     │  │
│   │   POST   /admin/users/{id}/verify/ # Verify user                   │  │
│   │   POST   /admin/users/{id}/ban/   # Ban user                       │   │
│   │   GET    /admin/assets/           # List all assets                 │  │
│   │   POST   /admin/assets/{id}/verify/ # Verify asset                  │  │
│   │   POST   /admin/assets/{id}/reject/ # Reject verification           │  │
│   │   GET    /admin/bookings/         # List all bookings               │  │
│   │   POST   /admin/bookings/{id}/override/ # Override booking         │  │
│   │   GET    /admin/contracts/        # List all contracts              │  │
│   │   POST   /admin/contracts/{id}/admin_sign/ # Admin sign contract   │  │
│   │   GET    /admin/disputes/         # List disputes                   │  │
│   │   POST   /admin/disputes/{id}/resolve/ # Resolve dispute          │  │
│   │   GET    /admin/audit/            # Get audit logs                   │  │
│   │   POST   /admin/audit/export/     # Export audit logs               │  │
│   │   GET    /admin/stats/            # Get platform statistics         │  │
│   │   POST   /admin/maintenance/      # Trigger maintenance             │  │
│   │                                                                      │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. WebSocket Architecture

### 9.1 WebSocket Endpoints

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      WEBSOCKET ARCHITECTURE                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   BASE WS URL: ws://localhost:8000/ws/                                       │
│   AUTHENTICATION: JWT token in connection params                             │
│   PROTOCOL: JSON                                                             │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                    MESSAGING (/ws/chat/)                             │  │
│   │                                                                      │  │
│   │   Connection:                                                        │  │
│   │   ws://localhost:8000/ws/chat/{thread_id}/?token={JWT}              │  │
│   │                                                                      │  │
│   │   Send:                                                              │  │
│   │   {                                                                  │  │
│   │     "type": "message",                                               │  │
│   │     "content": "Hello!",                                             │  │
│   │     "attachments": ["file_id_1", "file_id_2"]                        │  │
│   │   }                                                                  │  │
│   │                                                                      │  │
│   │   Receive:                                                           │  │
│   │   {                                                                  │  │
│   │     "type": "message",                                               │  │
│   │     "id": 123,                                                       │  │
│   │     "sender": {"id": 1, "username": "john"},                          │  │
│   │     "content": "Hello!",                                             │  │
│   │     "timestamp": "2024-01-15T10:30:00Z",                             │  │
│   │     "attachments": [...]                                             │  │
│   │   }                                                                  │  │
│   │                                                                      │  │
│   │   Typing Indicator:                                                  │  │
│   │   { "type": "typing", "user_id": 1, "is_typing": true }               │  │
│   │                                                                      │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                  NOTIFICATIONS (/ws/notifications/)                  │  │
│   │                                                                      │  │
│   │   Connection:                                                        │  │
│   │   ws://localhost:8000/ws/notifications/?token={JWT}                 │  │
│   │                                                                      │  │
│   │   Receive:                                                           │  │
│   │   {                                                                  │  │
│   │     "type": "notification",                                         │  │
│   │     "id": 456,                                                       │  │
│   │     "category": "booking",                                           │  │
│   │     "title": "Booking Confirmed",                                    │  │
│   │     "message": "Your booking for 'Apartment' has been confirmed",   │  │
│   │     "data": {"booking_id": 789},                                     │  │
│   │     "timestamp": "2024-01-15T10:30:00Z"                             │  │
│   │   }                                                                  │  │
│   │                                                                      │  │
│   │   Types:                                                             │  │
│   │   • booking.created                                                 │  │
│   │   • booking.confirmed                                               │  │
│   │   • booking.started                                                 │  │
│   │   • booking.completed                                               │  │
│   │   • ride.departing                                                  │  │
│   │   • ride.arrived                                                    │  │
│   │   • message.received                                               │  │
│   │   • contract.pending_accept                                         │  │
│   │   • payment.released                                               │  │
│   │   • rating.received                                                 │  │
│   │   • dispute.update                                                 │  │
│   │                                                                      │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                    BOOKING UPDATES (/ws/bookings/)                  │  │
│   │                                                                      │  │
│   │   Connection:                                                        │  │
│   │   ws://localhost:8000/ws/bookings/{booking_id}/?token={JWT}         │  │
│   │                                                                      │  │
│   │   Receive:                                                           │  │
│   │   {                                                                  │  │
│   │     "type": "status_update",                                         │  │
│   │     "status": "ACTIVE",                                             │  │
│   │     "timestamp": "2024-01-15T10:30:00Z",                             │  │
│   │     "message": "Your booking has started"                             │  │
│   │   }                                                                  │  │
│   │                                                                      │  │
│   │   Location Update (for active bookings):                            │  │
│   │   {                                                                  │  │
│   │     "type": "location_update",                                      │  │
│   │     "latitude": 37.7749,                                            │  │
│   │     "longitude": -122.4194,                                         │  │
│   │     "accuracy": 10.0,                                                │  │
│   │     "timestamp": "2024-01-15T10:30:00Z"                             │  │
│   │   }                                                                  │  │
│   │                                                                      │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                    RIDE TRACKING (/ws/rides/)                        │  │
│   │                                                                      │  │
│   │   Connection:                                                        │  │
│   │   ws://localhost:8000/ws/rides/{ride_id}/?token={JWT}               │  │
│   │                                                                      │  │
│   │   Receive:                                                           │  │
│   │   {                                                                  │  │
│   │     "type": "ride_update",                                          │  │
│   │     "status": "IN_TRANSIT",                                          │  │
│   │     "current_stop": 3,                                               │  │
│   │     "next_stop": 4,                                                  │  │
│   │     "estimated_arrival": "2024-01-15T11:00:00Z",                    │  │
│   │     "driver_location": {"lat": 37.7749, "lng": -122.4194}           │  │
│   │   }                                                                  │  │
│   │                                                                      │  │
│   │   Stop Arrival:                                                      │  │
│   │   {                                                                  │  │
│   │     "type": "stop_arrival",                                          │  │
│   │     "stop_id": 3,                                                    │  │
│   │     "stop_name": "Central Park",                                     │  │
│   │     "passengers_arriving": [1, 2, 3],                                │  │
│   │     "passengers_boarding": [4, 5]                                   │  │
│   │   }                                                                  │  │
│   │                                                                      │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 10. Infrastructure Architecture

### 10.1 Docker Compose Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      DOCKER COMPOSE ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    DOCKER COMPOSE.YML                               │   │
│   │                                                                     │   │
│   │   version: '3.8'                                                    │   │
│   │                                                                     │   │
│   │   services:                                                        │   │
│   │     redis:                                                          │   │
│   │       image: redis:7-alpine                                         │   │
│   │       ports:                                                        │   │
│   │         - "6379:6379"                                               │   │
│   │       volumes:                                                       │   │
│   │         - redis_data:/data                                          │   │
│   │       command: redis-server --appendonly yes --maxmemory 256mb      │   │
│   │       healthcheck:                                                  │   │
│   │         test: ["CMD", "redis-cli", "ping"]                          │   │
│   │         interval: 10s                                                │   │
│   │         timeout: 5s                                                 │   │
│   │         retries: 3                                                 │   │
│   │                                                                     │   │
│   │     celery-worker:                                                  │   │
│   │       build: .                                                      │   │
│   │       command: celery -A kiboss worker -l info                     │   │
│   │       volumes:                                                       │   │
│   │         - .:/app                                                    │   │
│   │       depends_on:                                                   │   │
│   │         redis:                                                      │   │
│   │           condition: service_healthy                                │   │
│   │       environment:                                                  │   │
│   │         - CELERY_BROKER_URL=redis://redis:6379/0                    │   │
│   │         - CELERY_RESULT_URL=redis://redis:6379/1                     │   │
│   │                                                                     │   │
│   │     celery-beat:                                                    │   │
│   │       build: .                                                      │   │
│   │       command: celery -A kiboss beat -l info                       │   │
│   │       volumes:                                                       │   │
│   │         - .:/app                                                    │   │
│   │       depends_on:                                                   │   │
│   │         redis:                                                      │   │
│   │           condition: service_healthy                                │   │
│   │       environment:                                                  │   │
│   │         - CELERY_BROKER_URL=redis://redis:6379/0                    │   │
│   │                                                                     │   │
│   │   volumes:                                                          │   │
│   │     redis_data:                                                     │   │
│   │                                                                     │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    LOCAL DEVELOPMENT SETUP                           │   │
│   │                                                                     │   │
│   │   Django Application (run directly, not in Docker):                │   │
│   │   • python manage.py runserver 0.0.0.0:8000                        │   │
│   │   • Connected to Redis on localhost:6379                           │   │
│   │   • SQLite at BASE_DIR/db.sqlite3                                  │   │
│   │   • Media files at BASE_DIR/media/                                 │   │
│   │   • Static files at BASE_DIR/static/                               │   │
│   │                                                                     │   │
│   │   Celery Workers (run directly, not in Docker):                    │   │
│   │   • celery -A kiboss worker -l info --pool=solo                   │   │
│   │   • celery -A kiboss beat -l info                                 │   │
│   │                                                                     │   │
│   │   Redis (Docker):                                                   │   │
│   │   • docker-compose up -d redis                                     │   │
│   │   • Accessible at localhost:6379                                   │   │
│   │                                                                     │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 11. Performance Architecture

### 11.1 Caching Strategy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      CACHING STRATEGY                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   CACHE TIERS:                                                               │
│   ────────────                                                               │
│                                                                              │
│   L1: In-Memory (Process)                                                    │
│   • Local cache (functools.lru_cache)                                       │
│   • For frequently accessed, rarely changing data                           │
│   • Example: Asset categories, configuration                                 │
│                                                                              │
│   L2: Redis (Distributed)                                                    │
│   • Hot paths: Asset listings, user profiles, booking details                │
│   • Cache invalidation on writes                                              │
│   • TTL-based expiration                                                     │
│                                                                              │
│   L3: Database (SQLite)                                                      │
│   • Indexed queries                                                          │
│   • Denormalized aggregations                                                │
│   • Materialized views (if needed)                                           │
│                                                                              │
│   CACHE PATTERNS:                                                            │
│   ───────────────                                                            │
│                                                                              │
│   Cache-Aside (for reads):                                                   │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                                                                     │  │
│   │   def get_asset(asset_id):                                          │  │
│   │       cache_key = f"asset:{asset_id}"                               │  │
│   │       asset = redis.get(cache_key)                                  │  │
│   │       if asset is None:                                              │  │
│   │           asset = db.query(Asset).get(asset_id)                     │  │
│   │           redis.setex(cache_key, 300, asset)  # 5 min TTL          │  │
│   │       return asset                                                   │  │
│   │                                                                     │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│   Write-Through (for critical data):                                         │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                                                                     │  │
│   │   def update_asset(asset_id, data):                                │  │
│   │       db.transaction:                                               │  │
│   │           asset = db.query(Asset).get(asset_id)                     │  │
│   │           asset.update(data)                                        │  │
│   │           asset.save()                                              │  │
│   │       redis.setex(f"asset:{asset_id}", 300, asset)  # Update cache │  │
│   │       invalidate_related_caches(asset_id)                           │  │
│   │                                                                     │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│   CACHE KEY STRUCTURE:                                                       │
│   ───────────────────                                                        │
│                                                                              │
│   Pattern: {prefix}:{entity}:{id}:{variant}                                   │
│                                                                              │
│   Examples:                                                                  │
│   • cache:asset:123:basic          # Basic asset info                       │
│   • cache:asset:123:full           # Full asset with pricing               │
│   • cache:asset:list:page=2&type=room&sort=price  # Paginated list         │
│   • cache:user:456:profile         # User profile                          │
│   • cache:user:456:dashboard       # Dashboard data                         │
│   • cache:booking:789:details       # Booking details                        │
│                                                                              │
│   TTL STRATEGY:                                                              │
│   ────────────                                                                │
│                                                                              │
│   Entity          Cache Type    TTL        Invalidation                      │
│   ──────────────────────────────────────────────────────────────────────────│
│   Asset           List          60s       On create/update/delete            │
│   Asset           Detail        300s      On update                          │
│   User Profile    Detail        600s      On profile update                  │
│   Booking         Detail        60s       On status change                   │
│   Ride Schedule   List          300s      On schedule update                 │
│   Configuration   Static        3600s     On config change                    │
│                                                                              │
│   INVALIDATION RULES:                                                        │
│   ──────────────────                                                         │
│                                                                              │
│   On Asset Update:                                                           │
│   • Invalidate cache:asset:{id}:*                                           │
│   • Invalidate cache:asset:list:* (full list)                               │
│   • Invalidate cache:asset:list:{filters} (matching filters)               │
│                                                                              │
│   On Booking State Change:                                                   │
│   • Invalidate cache:booking:{id}:*                                         │
│   • Invalidate asset availability cache                                      │
│                                                                              │
│   On User Update:                                                            │
│   • Invalidate cache:user:{id}:*                                            │
│   • Invalidate any caches containing user data                               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 12. Error Handling Architecture

### 12.1 Error Response Format

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ERROR HANDLING ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   STANDARD ERROR RESPONSE:                                                   │
│   ───────────────────────                                                    │
│                                                                              │
│   {                                                                          │   │
│     "error": {                                                               │   │
│       "code": "ERROR_CODE",          // Machine-readable code             │   │
│       "message": "Human readable message",                                  │   │
│       "details": {                    // Additional context (optional)     │   │
│         "field": "email",                                                     │   │
│         "reason": "already_exists"                                          │   │
│       },                                                                   │   │
│       "request_id": "uuid",           // For correlation                  │   │
│       "timestamp": "2024-01-15T10:30:00Z"                                   │   │
│     }                                                                        │   │
│   }                                                                          │   │
│                                                                              │
│   HTTP STATUS CODES:                                                         │
│   ────────────────                                                           │
│                                                                              │
│   400 Bad Request          - Invalid input data                             │   │
│   401 Unauthorized         - Missing or invalid JWT                         │   │
│   403 Forbidden            - Insufficient permissions                        │   │
│   404 Not Found            - Resource doesn't exist                          │   │
│   409 Conflict             - Business rule violation                          │   │
│   422 Unprocessable Entity - Validation error                                │   │
│   429 Too Many Requests    - Rate limit exceeded                            │   │
│   500 Internal Server Error - Unexpected error                              │   │
│   503 Service Unavailable  - Temporary outage                               │   │
│                                                                              │
│   BUSINESS ERROR CODES:                                                      │
│   ────────────────────                                                       │
│                                                                              │
│   ASSET_ERRORS:                                                              │
│   • ASSET001 - Asset not found                                               │   │
│   • ASSET002 - Asset not available                                          │   │
│   • ASSET003 - Asset verification required                                   │   │
│   • ASSET004 - Asset not owned by user                                       │   │
│                                                                              │
│   BOOKING_ERRORS:                                                            │
│   • BOOK001 - Booking not found                                              │   │
│   • BOOK002 - Time slot not available                                        │   │
│   • BOOK003 - Double booking detected                                       │   │
│   • BOOK004 - Invalid booking state transition                               │   │
│   • BOOK005 - Booking expired                                               │   │
│   • BOOK006 - Late cancellation penalty                                      │   │
│                                                                              │
│   PAYMENT_ERRORS:                                                            │


│   • PAY001 - Payment not found                                               │   │
│   • PAY002 - Payment failed                                                  │   │
│   • PAY003 - Payment already processed                                       │   │
│   • PAY004 - Insufficient funds                                              │   │
│   • PAY005 - Escrow hold failed                                             │   │
│   • PAY006 - Refund failed                                                   │   │
│                                                                              │
│   CONTRACT_ERRORS:                                                           │
│   • CONT001 - Contract not found                                             │   │
│   • CONT002 - Contract already accepted                                     │   │
│   • CONT003 - Contract acceptance required                                   │   │
│   • CONT004 - Contract modification not allowed                              │   │
│                                                                              │
│   RIDE_ERRORS:                                                               │
│   • RIDE001 - Ride not found                                                 │   │
│   • RIDE002 - Seat not available                                             │   │
│   • RIDE003 - Seat already booked                                           │   │
│   • RIDE004 - Cannot book past departure                                     │   │
│   • RIDE005 - Ride already departed                                          │   │
│                                                                              │
│   MESSAGING_ERRORS:                                                          │
│   • MSG001 - Thread not found                                                │   │
│   • MSG002 - Not authorized to access thread                                 │   │
│   • MSG003 - Thread locked                                                  │   │
│   • MSG004 - Rate limit exceeded                                             │   │
│   • MSG005 - Message too long                                                │   │
│   • MSG006 - Attachment not allowed                                          │   │
│                                                                              │
│   AUTH_ERRORS:                                                               │
│   • AUTH001 - Invalid credentials                                            │   │
│   • AUTH002 - Account disabled                                               │   │
│   • AUTH003 - Email not verified                                             │   │
│   • AUTH004 - Token expired                                                  │   │
│   • AUTH005 - Token revoked                                                  │   │
│   • AUTH006 - Password too weak                                              │   │
│   • AUTH007 - Email already exists                                           │   │
│                                                                              │
│   RATE_LIMIT_ERRORS:                                                         │
│   • RATE001 - Rate limit exceeded                                            │   │
│   • RATE002 - Too many login attempts                                        │   │
│   • RATE003 - API quota exceeded                                             │   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 13. Monitoring & Observability

### 13.1 Logging Structure

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      LOGGING ARCHITECTURE                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   LOG FORMAT (JSON):                                                         │
│   ─────────────────                                                          │
│                                                                              │
│   {                                                                          │   │
│     "timestamp": "2024-01-15T10:30:00.123Z",                                │   │
│     "level": "INFO",                                                         │   │
│     "logger": "kiboss.booking.services",                                     │   │
│     "message": "Booking created",                                            │   │
│     "request_id": "uuid",                                                   │   │
│     "user_id": 123,                                                          │   │
│     "span_id": "abc123",                                                     │   │
│     "trace_id": "xyz789",                                                    │   │
│     "context": {                                                             │   │
│       "booking_id": 456,                                                    │   │
│       "asset_id": 789,                                                      │   │
│       "duration_hours": 4                                                   │   │
│     }                                                                        │   │
│   }                                                                          │   │
│                                                                              │
│   LOG LEVELS:                                                                │
│   ───────────                                                                │
│                                                                              │
│   DEBUG    - Detailed debugging information                                 │   │
│   INFO     - Normal operational events                                      │   │
│   WARNING  - Unexpected but recoverable issues                              │   │
│   ERROR    - Errors and exceptions                                          │   │
│   CRITICAL - System-level failures                                          │   │
│                                                                              │
│   KEY LOG EVENTS:                                                            │
│   ──────────────                                                             │
│                                                                              │
│   SECURITY:                                                                  │
│   • Authentication success/failure                                            │   │
│   • Authorization failures                                                   │   │
│   • Suspicious activity (rapid requests, unusual patterns)                 │   │
│   • Admin actions with justification                                         │   │
│   │   • Token blacklisting                                                  │   │
│   │   • Password changes                                                    │   │
│   │   • Permission changes                                                  │   │
│                                                                              │
│   BUSINESS:                                                                   │
│   • Booking state transitions                                                │   │
│   • Payment processing                                                        │   │
│   • Contract generation/acceptance                                           │   │
│   • Dispute creation/resolution                                              │   │
│   • Rating submissions                                                        │   │
│                                                                              │
│   SYSTEM:                                                                     │
│   │   • Celery task starts/completes/fails                                 │   │
│   │   • Redis connection issues                                             │   │
│   │   • Database transaction rollbacks                                     │   │
│   │   • Cache invalidation                                                   │   │
│   │   • External service calls                                               │   │
│   │                                                                      │   │
│   PERFORMANCE:                                                                │
│   │   • Slow queries (>100ms)                                               │   │
│   │   • Slow API endpoints (>500ms)                                         │   │
│   │   • Celery task execution times                                         │   │
│   │   • Cache hit/miss ratios                                                │   │
│   │                                                                      │   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 14. Summary

This architecture document provides the comprehensive blueprint for KIBOSS:

1. **Layered Architecture**: Clear separation between client, API gateway, application services, domain models, and data persistence.

2. **Event-Driven Design**: Celery for async processing, Django Channels for real-time WebSocket communication.

3. **State Machine**: Explicit booking lifecycle with atomic transitions.

4. **Redis Integration**: Caching, distributed locking, rate limiting, and pub/sub.

5. **Security First**: JWT authentication, RBAC, rate limiting, audit logging.

6. **Extensibility**: Universal asset model supports any rental type without hard-coded categories.

7. **Local-First**: All services run locally (Django, Redis via Docker, SQLite).

The next step is to implement the Domain Models (Step 2) based on this architecture.
