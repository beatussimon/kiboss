"""
Test Data Population Script for KIBOSS

This script creates sample data for testing the system:
- Users (drivers, renters, owners)
- Assets (vehicles, rooms, tools)
- Rides (with stops and bookings)
- Bookings (rental bookings)
- Reviews and ratings
"""

import random
from datetime import datetime, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from kiboss.apps.users.models import User, UserProfile, TrustScore
from kiboss.apps.assets.models import Asset, AssetType, AssetPhoto
from kiboss.apps.rides.models import (
    Ride, RideStop, SeatBooking, SeatBookingStatus, RideStatus, RideSchedule
)
from kiboss.apps.bookings.models import Booking, BookingStatus, BookingTimeline
from kiboss.apps.payments.models import Payment, PaymentStatus
from kiboss.apps.contracts.models import Contract, ContractStatus
from kiboss.apps.ratings.models import Rating, RatingCategory


# Sample data
FIRST_NAMES = ['John', 'Jane', 'Mike', 'Sarah', 'David', 'Emily', 'Chris', 'Lisa', 'Tom', 'Anna']
LAST_NAMES = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez']

CITIES = [
    ('New York', 'NY', 40.7128, -74.0060),
    ('Los Angeles', 'CA', 34.0522, -118.2437),
    ('Chicago', 'IL', 41.8781, -87.6298),
    ('Houston', 'TX', 29.7604, -95.3698),
    ('Phoenix', 'AZ', 33.4484, -112.0740),
    ('San Francisco', 'CA', 37.7749, -122.4194),
    ('Seattle', 'WA', 47.6062, -122.3321),
    ('Boston', 'MA', 42.3601, -71.0589),
    ('Denver', 'CO', 39.7392, -104.9903),
    ('Miami', 'FL', 25.7617, -80.1918),
]

VEHICLE_MAKES = [
    ('Toyota', ['Camry', 'Corolla', 'RAV4', 'Highlander']),
    ('Honda', ['Civic', 'Accord', 'CR-V', 'Pilot']),
    ('Ford', ['F-150', 'Mustang', 'Explorer', 'Escape']),
    ('Chevrolet', ['Malibu', 'Equinox', 'Silverado', 'Tahoe']),
    ('BMW', ['3 Series', '5 Series', 'X3', 'X5']),
    ('Mercedes-Benz', ['C-Class', 'E-Class', 'GLC', 'GLE']),
]

ROOM_NAMES = [
    'Downtown Loft', 'Sunny Studio', 'Cozy Apartment', 'Luxury Suite',
    'Modern Condo', 'Garden View Room', 'City Center Studio', 'Executive Suite'
]

TOOL_NAMES = [
    'Professional Camera Kit', 'Power Drill Set', 'Pressure Washer',
    'Extension Ladder', 'Circular Saw', 'Oscillating Multi-Tool'
]


class Command(BaseCommand):
    help = 'Create test data for KIBOSS'

    def add_arguments(self, parser):
        parser.add_argument(
            '--users', type=int, default=10,
            help='Number of users to create'
        )
        parser.add_argument(
            '--rides', type=int, default=20,
            help='Number of rides to create'
        )
        parser.add_argument(
            '--bookings', type=int, default=15,
            help='Number of bookings to create'
        )

    def handle(self, *args, **options):
        num_users = options['users']
        num_rides = options['rides']
        num_bookings = options['bookings']

        self.stdout.write('Creating test data...')

        # Create users
        users = self.create_users(num_users)
        self.stdout.write(f'Created {len(users)} users')

        # Create assets
        assets = self.create_assets(users)
        self.stdout.write(f'Created {len(assets)} assets')

        # Create rides
        rides = self.create_rides(users, assets, num_rides)
        self.stdout.write(f'Created {len(rides)} rides')

        # Create bookings
        bookings = self.create_bookings(users, assets, num_bookings)
        self.stdout.write(f'Created {len(bookings)} bookings')

        # Create some completed rides and bookings for historical data
        self.create_completed_data(users, assets)

        self.stdout.write(self.style.SUCCESS('Test data creation complete!'))

    def create_users(self, count):
        """Create sample users."""
        users = []

        for i in range(count):
            first_name = random.choice(FIRST_NAMES)
            last_name = random.choice(LAST_NAMES)
            email = f'testuser{i+1}@example.com'
            
            # Check if user already exists
            existing_user = User.objects.filter(email=email).first()
            if existing_user:
                users.append(existing_user)
                continue
            
            # Create user
            user = User.objects.create_user(
                email=email,
                password='testpass123',
                first_name=first_name,
                last_name=last_name,
                is_email_verified=random.choice([True, True, True, False]),
                is_phone_verified=random.choice([True, True, False, False]),
                is_identity_verified=random.choice([True, False, False, False]),
                trust_score=Decimal(str(random.uniform(40, 100))),
                total_ratings_count=random.randint(0, 50),
            )

            # Create profile
            city = random.choice(CITIES)
            profile = UserProfile.objects.create(
                user=user,
                phone=f'+1{random.randint(2000000000, 9999999999)}',
                bio=f'Test user - {first_name} {last_name}',
                city=city[0],
                state=city[1],
                latitude=city[2],
                longitude=city[3],
                total_rides_as_driver=random.randint(0, 30),
                total_rides_as_passenger=random.randint(0, 20),
            )

            # Create trust score
            trust = TrustScore.objects.create(
                user=user,
                reliability_score=Decimal(str(random.uniform(50, 100))),
                communication_score=Decimal(str(random.uniform(50, 100))),
                cleanliness_score=Decimal(str(random.uniform(50, 100))),
                timeliness_score=Decimal(str(random.uniform(50, 100))),
                overall_score=Decimal(str(random.uniform(50, 100))),
                completed_bookings=random.randint(0, 20),
                cancelled_bookings=random.randint(0, 5),
            )

            users.append(user)

        # Create a few verified drivers
        for i in range(3):
            first_name = random.choice(FIRST_NAMES)
            last_name = random.choice(LAST_NAMES)
            email = f'driver{i+1}@example.com'
            
            # Check if user already exists
            existing_user = User.objects.filter(email=email).first()
            if existing_user:
                users.append(existing_user)
                continue
            
            user = User.objects.create_user(
                email=email,
                password='testpass123',
                first_name=first_name,
                last_name=last_name,
                is_email_verified=True,
                is_phone_verified=True,
                is_identity_verified=True,
                trust_score=Decimal(str(random.uniform(80, 100))),
                total_ratings_count=random.randint(20, 100),
            )

            city = random.choice(CITIES)
            profile = UserProfile.objects.create(
                user=user,
                phone=f'+1{random.randint(2000000000, 9999999999)}',
                bio=f'Professional driver - {first_name} {last_name}',
                city=city[0],
                state=city[1],
                latitude=city[2],
                longitude=city[3],
                total_rides_as_driver=random.randint(50, 200),
            )

            TrustScore.objects.create(
                user=user,
                reliability_score=Decimal(str(random.uniform(80, 100))),
                communication_score=Decimal(str(random.uniform(80, 100))),
                cleanliness_score=Decimal(str(random.uniform(80, 100))),
                timeliness_score=Decimal(str(random.uniform(80, 100))),
                overall_score=Decimal(str(random.uniform(80, 100))),
                completed_bookings=random.randint(50, 200),
            )

            users.append(user)

        return users

    def create_assets(self, users):
        """Create sample assets."""
        assets = []

        # Ensure we have enough users
        if len(users) < 5:
            users *= 3

        # Create vehicles
        for i in range(15):
            make, models = random.choice(VEHICLE_MAKES)
            model = random.choice(models)
            year = random.randint(2015, 2024)
            city = random.choice(CITIES)
            
            asset = Asset.objects.create(
                name=f'{year} {make} {model}',
                description=f'Clean, reliable {year} {make} {model} - perfect for your trip',
                asset_type=AssetType.VEHICLE,
                owner=random.choice(users),
                city=city[0],
                state=city[1],
                country='US',
                latitude=city[2],
                longitude=city[3],
                verification_status=random.choice(['VERIFIED', 'VERIFIED', 'PENDING', 'UNVERIFIED']),
                is_active=True,
                is_listed=True,
                total_bookings=random.randint(0, 30),
                average_rating=Decimal(str(random.uniform(3.5, 5.0))),
                total_reviews=random.randint(0, 50),
                properties={
                    'make': make,
                    'model': model,
                    'year': year,
                    'color': random.choice(['Black', 'White', 'Silver', 'Blue', 'Red']),
                    'seats': random.randint(4, 8),
                    'transmission': random.choice(['Automatic', 'Manual']),
                    'fuel_type': random.choice(['Gasoline', 'Electric', 'Hybrid']),
                    'mileage': random.randint(10000, 100000),
                }
            )
            assets.append(asset)

        # Create rooms
        for i in range(8):
            name = random.choice(ROOM_NAMES)
            city = random.choice(CITIES)
            
            asset = Asset.objects.create(
                name=name,
                description=f'Beautiful {name.lower()} in the heart of {city[0]}',
                asset_type=AssetType.ROOM,
                owner=random.choice(users),
                city=city[0],
                state=city[1],
                country='US',
                latitude=city[2],
                longitude=city[3],
                verification_status=random.choice(['VERIFIED', 'PENDING']),
                is_active=True,
                is_listed=True,
                total_bookings=random.randint(0, 20),
                average_rating=Decimal(str(random.uniform(3.8, 5.0))),
                total_reviews=random.randint(0, 30),
                properties={
                    'bedrooms': random.randint(1, 3),
                    'bathrooms': random.randint(1, 2),
                    'sqft': random.randint(400, 2000),
                    'amenities': ['WiFi', 'Air Conditioning', 'Kitchen', 'Parking'],
                }
            )
            assets.append(asset)

        # Create tools
        for i in range(6):
            name = random.choice(TOOL_NAMES)
            city = random.choice(CITIES)
            
            asset = Asset.objects.create(
                name=name,
                description=f'Professional {name.lower()} - well maintained',
                asset_type=AssetType.TOOL,
                owner=random.choice(users),
                city=city[0],
                state=city[1],
                country='US',
                latitude=city[2],
                longitude=city[3],
                verification_status='UNVERIFIED',
                is_active=True,
                is_listed=True,
                total_bookings=random.randint(0, 10),
                average_rating=Decimal(str(random.uniform(3.5, 5.0))),
                total_reviews=random.randint(0, 15),
                properties={
                    'brand': random.choice(['DeWalt', 'Makita', 'Bosch', 'Milwaukee']),
                    'condition': random.choice(['Like New', 'Good', 'Fair']),
                    'accessories': True,
                }
            )
            assets.append(asset)

        return assets

    def create_rides(self, users, assets, count):
        """Create sample rides."""
        rides = []

        # Filter vehicles and drivers
        vehicles = [a for a in assets if a.asset_type == AssetType.VEHICLE]
        drivers = [u for u in users if u.trust_score >= 70]

        if not vehicles or not drivers:
            return rides

        for i in range(count):
            driver = random.choice(drivers)
            vehicle = random.choice(vehicles)
            
            # Pick random cities for route
            origin_city = random.choice(CITIES)
            dest_city = random.choice([c for c in CITIES if c != origin_city])
            
            # Set departure time (next 7 days)
            departure_time = timezone.now() + timedelta(
                days=random.randint(0, 7),
                hours=random.randint(6, 20),
                minutes=random.randint(0, 59)
            )

            ride = Ride.objects.create(
                driver=driver,
                vehicle_asset=vehicle,
                status=random.choice([RideStatus.SCHEDULED, RideStatus.OPEN, RideStatus.OPEN]),
                route_name=f'{origin_city[0]} to {dest_city[0]}',
                origin=origin_city[0],
                destination=dest_city[0],
                departure_time=departure_time,
                estimated_arrival=departure_time + timedelta(hours=random.randint(2, 12)),
                total_seats=random.randint(2, 6),
                seat_price=Decimal(str(random.uniform(15, 80))),
                currency='USD',
                reserved_seats=random.randint(0, 3),
                confirmed_seats=random.randint(0, 3),
                vehicle_description=str(vehicle.properties.get('year', '')) + ' ' + 
                                   str(vehicle.properties.get('make', '')) + ' ' +
                                   str(vehicle.properties.get('model', '')),
                vehicle_color=vehicle.properties.get('color', ''),
            )

            # Add stops
            num_stops = random.randint(1, 3)
            for j in range(num_stops):
                stop_city = random.choice(CITIES)
                RideStop.objects.create(
                    ride=ride,
                    stop_type=random.choice(['PICKUP', 'DROPOFF', 'BOTH']),
                    name=f'{stop_city[0]} {random.choice(["Station", "Center", "Plaza", "Mall"])}',
                    address=f'123 Main St, {stop_city[0]}',
                    latitude=stop_city[2],
                    longitude=stop_city[3],
                    stop_order=j + 1,
                )

            rides.append(ride)

        return rides

    def create_bookings(self, users, assets, count):
        """Create sample bookings."""
        bookings = []

        for i in range(count):
            renter = random.choice(users)
            asset = random.choice(assets)

            # Set booking time
            start_time = timezone.now() + timedelta(
                days=random.randint(1, 14),
                hours=random.randint(8, 18)
            )
            end_time = start_time + timedelta(
                hours=random.randint(2, 72)
            )

            unit_price = Decimal(str(random.uniform(20, 200)))
            quantity = random.randint(1, 3)
            days = (end_time - start_time).days or 1
            subtotal = unit_price * quantity * days
            service_fee = subtotal * Decimal('0.10')
            total_price = subtotal + service_fee

            booking = Booking.objects.create(
                renter=renter,
                asset=asset,
                status=random.choice([BookingStatus.PENDING, BookingStatus.CONFIRMED, BookingStatus.ACTIVE]),
                start_time=start_time,
                end_time=end_time,
                quantity=quantity,
                unit_price=unit_price,
                subtotal=subtotal,
                service_fee=service_fee,
                total_price=total_price,
                price_breakdown={
                    'unit_price': str(unit_price),
                    'quantity': quantity,
                    'days': days,
                    'subtotal': str(subtotal),
                    'service_fee': str(service_fee),
                    'total': str(total_price),
                }
            )

            bookings.append(booking)

        return bookings

    def create_completed_data(self, users, assets):
        """Create some completed rides and bookings for historical data."""
        completed_rides = Ride.objects.filter(status=RideStatus.OPEN)[:5]
        vehicles = [a for a in assets if a.asset_type == AssetType.VEHICLE]

        for ride in completed_rides:
            # Mark as completed
            ride.status = RideStatus.COMPLETED
            ride.actual_arrival = ride.estimated_arrival
            ride.save()

            # Create some completed seat bookings
            for seat_num in range(1, min(ride.confirmed_seats + 1, ride.total_seats + 1)):
                passenger = random.choice([u for u in users if u != ride.driver])
                SeatBooking.objects.create(
                    ride=ride,
                    passenger=passenger,
                    seat_number=seat_num,
                    status=SeatBookingStatus.COMPLETED,
                    price=ride.seat_price,
                )

        # Create some completed bookings
        for asset in assets[:5]:
            if asset.asset_type not in [AssetType.ROOM, AssetType.TOOL]:
                continue
            renter = random.choice(users)
            start_time = timezone.now() - timedelta(days=random.randint(3, 30))
            end_time = start_time + timedelta(hours=random.randint(4, 48))

            booking = Booking.objects.create(
                renter=renter,
                asset=asset,
                status=BookingStatus.COMPLETED,
                start_time=start_time,
                end_time=end_time,
                quantity=random.randint(1, 2),
                unit_price=Decimal(str(random.uniform(30, 150))),
                subtotal=Decimal(str(random.uniform(100, 1000))),
                service_fee=Decimal(str(random.uniform(10, 100))),
                total_price=Decimal(str(random.uniform(110, 1100))),
                completed_at=end_time,
            )

            # Create payment
            Payment.objects.create(
                booking=booking,
                amount=booking.total_price,
                status=PaymentStatus.ESCROW,
                payment_method=random.choice(['CREDIT_CARD', 'BANK_TRANSFER']),
                zenopay_transaction_id=f'txn_{booking.id}_completed',
            )

            # Create contract
            Contract.objects.create(
                booking=booking,
                status=ContractStatus.ACCEPTED,
                renter_accepted_at=start_time - timedelta(hours=1),
            )

            # Create rating
            Rating.objects.create(
                booking=booking,
                reviewer=renter,
                rated_user=asset.owner,
                rating_category=RatingCategory.OWNER_TO_RENTER,
                rating=random.randint(4, 5),
                comment='Great experience! Would recommend.',
            )

        self.stdout.write('Created historical completed data')
