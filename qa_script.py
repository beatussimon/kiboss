import os
import django
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kiboss.settings')
django.setup()

from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from kiboss.apps.rides.models import Ride, CargoBooking, SeatBooking, RideType

User = get_user_model()
driver, _ = User.objects.get_or_create(email='driver_qa@test.com', defaults={'first_name': 'Driver'})
passenger1, _ = User.objects.get_or_create(email='pass1_qa@test.com', defaults={'first_name': 'Pass1'})
passenger2, _ = User.objects.get_or_create(email='pass2_qa@test.com', defaults={'first_name': 'Pass2'})

client = APIClient(SERVER_NAME='localhost')
client.force_authenticate(user=passenger1)

print("--- Starting QA Scenarios ---")

# 1. Dual Creation
ride = Ride.objects.create(
    driver=driver,
    ride_type=RideType.PERSONAL,
    cargo_enabled=True,
    total_cargo=Decimal('50'),
    cargo_price=Decimal('2000'),
    total_seats=4,
    seat_price=Decimal('50000'),
    departure_time=timezone.now() + timedelta(days=1),
    route_name="Test Route",
    origin="A", destination="B"
)
print(f"1. Dual Creation: Success. Ride {ride.id}")

# 2. Dashboard Display
print(f"2. Dashboard Display: Seats {ride.get_available_seats()}/4, Cargo {ride.get_available_cargo()}/50kg")

# 3. Cargo Booking via API
resp3 = client.post('/api/v1/rides/cargo-bookings/', {'ride_id': str(ride.id), 'weight': 20}, format='json')
if resp3.status_code != 201:
    print(f"FAILED Cargo Booking: {resp3.data}")

# To simulate CONFIRMED we might need to update the model manually if API creates it as RESERVED
cb = CargoBooking.objects.get(id=resp3.data['id'])
cb.status = 'CONFIRMED'
cb.save()

# Note: The API sets reserved_cargo, but since we manually set CONFIRMED we should also move reserved->confirmed logic.
ride.refresh_from_db()
ride.confirmed_cargo += cb.weight
ride.reserved_cargo -= cb.weight
ride.save()

ride.refresh_from_db()
print(f"3. Cargo Booking API: Available Cargo {ride.get_available_cargo()}kg. Status: {ride.status} (Code: {resp3.status_code})")

# 4. Seat Booking via API
for i in range(1, 5):
    # Depending on how the API logs the passenger, we just use the authenticated client
    resp4 = client.post(f'/api/v1/rides/trips/{ride.id}/book/', {'seat_number': i, 'payment_method': 'card'}, format='json')
    if resp4.status_code not in (200, 201):
        print(f"FAILED Seat Booking for seat {i}: {resp4.data}")
    else:
        # Manually confirm for the test
        sb = SeatBooking.objects.get(id=resp4.data['id'])
        sb.status = 'CONFIRMED'
        sb.save()
        ride.refresh_from_db()
        ride.confirmed_seats += 1
        ride.reserved_seats -= 1
        ride.save()

ride.refresh_from_db()
print(f"4. Seat Booking API: Available Seats {ride.get_available_seats()}, Available Cargo {ride.get_available_cargo()}kg. Status: {ride.status}")

# 5. Status Shift
client.force_authenticate(user=passenger2)
resp5 = client.post('/api/v1/rides/cargo-bookings/', {'ride_id': str(ride.id), 'weight': 30}, format='json')
if resp5.status_code == 201:
    cb2 = CargoBooking.objects.get(id=resp5.data['id'])
    cb2.status = 'CONFIRMED'
    cb2.save()
    ride.refresh_from_db()
    ride.confirmed_cargo += cb2.weight
    ride.reserved_cargo -= cb2.weight
    
    print(f"DEBUG Before Save: seats {ride.confirmed_seats}/{ride.total_seats}, cargo {ride.confirmed_cargo}/{ride.total_cargo}")
    ride.save()
    print(f"DEBUG After Save: status {ride.status}")

ride.refresh_from_db()
print(f"5. Status Shift API: Cargo booked out. Status is {ride.status} (Expected: FULL) (Code: {resp5.status_code})")

# 6. Cancellation Revert via API or Model
# Since Kiboss doesn't expose a unified cancel endpoint right away in our snippet, we use the model method.
seat = SeatBooking.objects.filter(ride=ride).first()
seat.cancel()
ride.refresh_from_db()
print(f"6. Cancellation Revert: Seat cancelled. Status is {ride.status} (Expected: SCHEDULED). Available seats: {ride.get_available_seats()}")

# 7. Business Ride Bulk via API
business_ride = Ride.objects.create(
    driver=driver,
    ride_type=RideType.BUSINESS,
    cargo_enabled=False,
    total_seats=50,
    seat_price=Decimal('10000'),
    departure_time=timezone.now() + timedelta(days=1),
    route_name="Business Route",
    origin="C", destination="D"
)
print(f"7. Business Ride created with {business_ride.total_seats} seats.")
client.force_authenticate(user=passenger1)
resp7 = client.post(f'/api/v1/rides/trips/{business_ride.id}/bulk_book_seats/', {'quantity': 20}, format='json')
business_ride.refresh_from_db()
print(f"   Bulk Booking API Response: {resp7.status_code}")
print(f"   Available Seats post-bulk booking: {business_ride.get_available_seats()} (Expected 30)")

print("\n--- Testing Complete ---")
