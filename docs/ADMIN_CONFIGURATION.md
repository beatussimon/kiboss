# KIBOSS Django Admin Configuration

## Overview

This document describes the enhanced Django admin configuration for the KIBOSS project, which provides a fully-featured administrative interface with custom features for managing all aspects of the platform.

## Key Features

### 1. Custom Admin Site
- **Location**: `kiboss/apps/core/admin.py`
- **Features**: Custom branding, enhanced dashboard with statistics, quick action links

### 2. Enhanced Model Registration
All models across 12 apps are registered with optimized admin configurations:

| App | Models Registered | Key Features |
|-----|-------------------|--------------|
| Users | User, Device, BlacklistedToken | Trust scores, verification status |
| Assets | Asset, Photo, Pricing, Availability | Verification workflow |
| Bookings | Booking, Timeline, Lock | Status transitions |
| Rides | Ride, Stop, Schedule, Booking | Seat management |
| Payments | Payment, Dispute | Escrow tracking |
| Contracts | Contract, Version | Signature tracking |
| Messaging | Thread, Message, Attachment | Moderation tools |
| Notifications | Notification, Preference | Delivery status |
| Ratings | Rating, TrustDetails | Moderation workflow |
| RBAC | RolePermission, UserRole, AdminAction | Audit trail |
| Audits | AuditLog | Security logging |
| Social | Like, Follow | Social features |

### 3. Common Admin Features

#### List Display
Each model includes optimized `list_display` with:
- Key fields for identification
- Color-coded status badges
- Computed properties
- Timestamps

#### Filtering
`list_filter` options include:
- Status fields
- Date/time ranges
- Foreign key relationships
- Boolean flags

#### Search
`search_fields` include:
- Email addresses
- Names and titles
- UUIDs
- Related object identifiers

#### Pagination
- Default: 25 items per page
- Maximum show all: 200-2000 items depending on model

### 4. Inline Admin Classes

Stacked Inlines (for complex related data):
- UserProfileInline
- TrustScoreInline
- AssetAvailabilityInline
- AssetTimeGranularityInline

Tabular Inlines (for simple related data):
- DeviceInline
- AssetPhotoInline
- AssetPricingInline
- SeatBookingInline
- MessageInline

### 5. Custom Actions

Batch operations available across models:

**Users:**
- Export to CSV
- Block/Unblock users
- Verify email/phone/identity
- Activate/Deactivate

**Assets:**
- Export to CSV
- Verify/Reject assets
- Activate/Deactivate
- List/Unlist

**Bookings:**
- Export to CSV
- Confirm/Cancel bookings
- Activate/Complete bookings

**Rides:**
- Export to CSV
- Open rides for booking
- Cancel/Complete rides
- Confirm seat bookings

**Payments:**
- Export to CSV
- Authorize payments
- Release escrow
- Refund payments
- Freeze for dispute

**Disputes:**
- Export to CSV
- Open/Resolve disputes

### 6. Export Functionality

All models support CSV export via the `export_to_csv` action, which:
- Generates timestamped CSV files
- Includes all model fields
- Handles related object display

### 7. Color-Coded Status Badges

Status values are displayed with color coding:

**Success (Green):**
- VERIFIED, COMPLETED, RELEASED, RESOLVED, APPROVED, ACTIVE

**Warning (Yellow/Orange):**
- PENDING, ESCROW, MODERATION_PENDING, OPEN

**Danger (Red):**
- CANCELLED, REJECTED, FAILED, FROZEN, DISPUTED, BLOCKED

**Info (Blue):**
- SCHEDULED, IN_TRANSIT, AUTHORIZED, CONFIRMED

### 8. Custom Dashboard

**Location**: `templates/admin/index.html`

The dashboard includes:

#### Statistics Cards
- User statistics (total, active, blocked, verified)
- Asset statistics (total, active, pending verification)
- Booking statistics (total, active, revenue)
- Ride statistics (total, scheduled, in transit)
- Payment statistics (total, in escrow, released)
- Dispute statistics (total, open, resolved)

#### Quick Actions
Links to common admin tasks:
- Manage Users
- Manage Assets
- Manage Bookings
- Manage Rides
- View Disputes
- Audit Logs

#### System Status
Summary table showing pending items that need attention.

### 9. Performance Optimizations

All admin classes use:
- `select_related()` for ForeignKey relationships
- `prefetch_related()` for ManyToMany relationships
- Read-only fields for computed/sensitive data
- Efficient queryset optimization

### 10. Security Features

#### Read-Only Fields
- IDs (UUIDs)
- Timestamps (created_at, updated_at)
- Computed properties
- Sensitive data

#### Permission Checks
- Superuser-only fields (is_superuser, permissions)
- Delete protection for critical objects
- Admin action logging

#### Audit Logging
All admin actions are logged via the AuditMiddleware and can be viewed in the AuditLogs section.

## Usage

### Accessing the Admin

The admin is available at `/admin/` with the custom enhanced interface.

### Using Custom Actions

1. Select objects in the list view
2. Choose an action from the dropdown
3. Click "Go" to execute

### Exporting Data

1. Select objects (or all)
2. Choose "Export to CSV" from actions
3. Download the generated CSV file

### Viewing Statistics

The dashboard at `/admin/` automatically shows:
- Real-time statistics from each app
- Quick action buttons
- System status overview

## Customization

### Adding New Models

To register a new model:

```python
from django.contrib import admin
from .models import MyModel

@admin.register(MyModel)
class MyModelAdmin(admin.ModelAdmin):
    list_display = ['field1', 'field2', 'status']
    list_filter = ['status', 'created_at']
    search_fields = ['field1', 'field2']
    actions = ['export_to_csv']
```

### Modifying Status Colors

Edit the `status_badge` method in the admin class:

```python
def status_badge(self, obj):
    status_colors = {
        'NEW_STATUS': '#custom-color',
    }
    color = status_colors.get(obj.status, '#default-color')
    return format_html(
        '<span style="background-color: {};">{}</span>',
        color, obj.get_status_display()
    )
```

### Adding Dashboard Widgets

Edit `templates/admin/index.html` to add new widgets:

```html
<div class="kiboss-stat-card custom">
    <h3>Custom Widget</h3>
    <div class="value">{{ custom_stat }}</div>
</div>
```

## File Structure

```
backend/
├── templates/
│   └── admin/
│       ├── base_site.html      # Custom branding
│       └── index.html          # Dashboard with stats
├── kiboss/
│   ├── apps/
│   │   ├── core/
│   │   │   └── admin.py        # Custom admin site
│   │   ├── users/
│   │   │   └── admin.py       # User admin classes
│   │   ├── assets/
│   │   │   └── admin.py       # Asset admin classes
│   │   ├── bookings/
│   │   │   └── admin.py       # Booking admin classes
│   │   ├── rides/
│   │   │   └── admin.py       # Ride admin classes
│   │   ├── payments/
│   │   │   └── admin.py       # Payment admin classes
│   │   ├── contracts/
│   │   │   └── admin.py       # Contract admin classes
│   │   ├── messaging/
│   │   │   └── admin.py       # Messaging admin classes
│   │   ├── notifications/
│   │   │   └── admin.py       # Notification admin classes
│   │   ├── ratings/
│   │   │   └── admin.py       # Rating admin classes
│   │   ├── rbac/
│   │   │   └── admin.py       # RBAC admin classes
│   │   ├── audits/
│   │   │   └── admin.py       # Audit admin classes
│   │   └── social/
│   │       └── admin.py       # Social admin classes
│   └── urls.py                # Uses custom admin site
└── docs/
    └── ADMIN_CONFIGURATION.md  # This file
```

## Troubleshooting

### Models Not Registered
If models don't appear in admin:
1. Ensure `register_all_models()` is called
2. Check for import errors in admin.py files
3. Verify apps are in `INSTALLED_APPS`

### Statistics Not Loading
Dashboard statistics may show "N/A" if:
1. Database tables are empty
2. There are circular import issues
3. Database connection problems

### Styling Not Applied
Custom CSS requires:
1. Template files in correct location
2. Static files properly configured
3. No cache issues

## Best Practices

1. **Use select_related/prefetch_related** to avoid N+1 queries
2. **Set appropriate list_per_page** for large datasets
3. **Use readonly_fields** for sensitive data
4. **Add custom actions** for common batch operations
5. **Use color-coded badges** for quick status recognition
6. **Export regularly** for backup and reporting
