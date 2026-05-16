import random
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model
from kiboss.apps.assets.models import Asset, AssetPhoto, AssetPricing, AssetAvailability, AssetType, VerificationStatus, PromotedListing
from kiboss.apps.rides.models import Ride, RideStop, RideStatus
from kiboss.apps.bookings.models import Booking, BookingStatus
from kiboss.apps.payments.models import Payment, PaymentStatus
from kiboss.apps.ratings.models import Rating, RatingCategory

logger = logging.getLogger(__name__)
User = get_user_model()

class Command(BaseCommand):
    help = 'Populates the database with Tanzanian test data'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Clear existing data before populating')

    def handle(self, *args, **options):
        random.seed(42)  # deterministic
        
        if options.get('reset'):
            self.stdout.write('Clearing existing data...')
            Payment.objects.all().delete()
            Rating.objects.all().delete()
            from kiboss.apps.contracts.models import Contract
            Contract.objects.all().delete()
            from kiboss.apps.messaging.models import Thread
            Thread.objects.all().delete()
            from kiboss.apps.rides.models import SeatBooking, CargoBooking
            CargoBooking.objects.all().delete()
            SeatBooking.objects.all().delete()
            Booking.objects.all().delete()
            Ride.objects.all().delete()
            Asset.objects.all().delete()
            User.objects.filter(is_superuser=False).delete()
            self.stdout.write('Cleared existing data')

        # Define data constants
        CITIES = [
            ('Dar es Salaam', 'TZ', -6.7924, 39.2083),
            ('Arusha', 'TZ', -3.3869, 36.6830),
            ('Mwanza', 'TZ', -2.5164, 32.9175),
            ('Dodoma', 'TZ', -6.1630, 35.7516),
            ('Zanzibar', 'TZ', -6.1659, 39.2026),
            ('Moshi', 'TZ', -3.3349, 37.3407),
            ('Tanga', 'TZ', -5.0688, 39.0987),
            ('Morogoro', 'TZ', -6.8235, 37.6606),
            ('Iringa', 'TZ', -7.7706, 35.6926),
            ('Mbeya', 'TZ', -8.9000, 33.4500),
        ]

        FIRST_NAMES = [
            'Amina', 'Juma', 'Fatuma', 'Hassan', 'Zawadi', 'Bakari', 'Zuhura',
            'Rashid', 'Neema', 'Omari', 'Salma', 'Hamisi', 'Rehema', 'Saidi', 'Leila'
        ]
        LAST_NAMES = [
            'Mwangi', 'Kimani', 'Odhiambo', 'Mutua', 'Wanjiku', 'Otieno', 'Njoroge',
            'Kamau', 'Achieng', 'Chebet', 'Nzinga', 'Banda', 'Phiri', 'Dlamini', 'Sithole'
        ]

        ASSET_NAMES = {
            AssetType.HOTEL_ROOM: [
                'Deluxe Sea View Room', 'Standard Double Room', 'Executive Suite',
                'Garden View Room', 'Ocean Front Suite', 'Budget Single Room'
            ],
            AssetType.ENTIRE_HOME: [
                'Beachfront Bungalow', 'City Apartment', 'Stone Town House',
                'Garden Villa', 'Modern Studio in Masaki', 'Furnished Flat in Kinondoni'
            ],
            AssetType.RECORDING_STUDIO: [
                'Professional Recording Suite A', 'Budget Home Studio', 'Digital Production Room'
            ],
            AssetType.CONFERENCE_HALL: [
                'Executive Boardroom (20 pax)', 'Main Conference Hall (100 pax)', 'Training Room (30 pax)'
            ],
            AssetType.EVENT_VENUE: [
                'Beachside Wedding Venue', 'Rooftop Event Space', 'Garden Party Area',
                'Indoor Banquet Hall'
            ],
            AssetType.VEHICLE: [
                'Toyota Hiace (14-Seater)', 'Land Cruiser 4WD', 'Toyota Corolla Sedan',
                'Isuzu D-Max Pickup', 'Coaster Bus (30-Seater)'
            ],
            AssetType.HOT_DESK: [
                'Co-working Hot Desk – Kariakoo', 'Shared Workspace – Masaki Hub',
                'Open Desk – Posta Area'
            ],
            AssetType.TOOL: [
                'Power Generator (5KVA)', 'Scaffolding Set', 'Cement Mixer',
                'Pressure Washer', 'Extension Ladder'
            ],
        }

        ROUTES = [
            ('Dar es Salaam', 'Mwanza', 12),
            ('Dar es Salaam', 'Arusha', 7.5),
            ('Dar es Salaam', 'Dodoma', 4.5),
            ('Dar es Salaam', 'Moshi', 8),
            ('Arusha', 'Moshi', 1.5),
            ('Arusha', 'Nairobi', 5),
            ('Dar es Salaam', 'Zanzibar (Ferry Port)', 0.5),
            ('Mwanza', 'Bukoba', 8),
            ('Dodoma', 'Iringa', 3),
            ('Mbeya', 'Dar es Salaam', 10),
        ]

        self.stdout.write('Creating users...')
        # Superuser
        if not User.objects.filter(email='admin@kiboss.co.tz').exists():
            User.objects.create_superuser('admin@kiboss.co.tz', 'Admin@2025', first_name='Admin', last_name='Kiboss')

        # Create predictable specific users
        specific_users = [
            ('amina@example.co.tz', 'Amina', 'Mutua', 'PLUS'),
            ('juma@example.co.tz', 'Juma', 'Hamisi', 'FREE'),
            ('fatuma@example.co.tz', 'Fatuma', 'Njoroge', 'FREE'),
            ('hassan@example.co.tz', 'Hassan', 'Bakari', 'BUSINESS'),
            ('saidi@example.co.tz', 'Saidi', 'Mwangi', 'FREE')
        ]
        
        users = []
        for email, fn, ln, tier in specific_users:
            if not User.objects.filter(email=email).exists():
                u = User.objects.create_user(
                    email=email, password='Test@1234', first_name=fn, last_name=ln,
                    account_tier=tier, is_phone_verified=True
                )
                if tier == 'BUSINESS':
                    from kiboss.apps.users.models import CorporateProfile
                    CorporateProfile.objects.create(
                        user=u, company_name=f'{fn} Enterprises', verification_status='VERIFIED'
                    )
                users.append(u)
            else:
                users.append(User.objects.get(email=email))
                
        # Fill rest to 15
        for i in range(10):
            fn = random.choice(FIRST_NAMES)
            ln = random.choice(LAST_NAMES)
            email = f'{fn.lower()}.{ln.lower()}{i}@example.co.tz'
            if not User.objects.filter(email=email).exists():
                u = User.objects.create_user(
                    email=email, password='Test@1234', first_name=fn, last_name=ln,
                    account_tier=random.choice(['FREE', 'PLUS', 'FREE']), 
                    is_phone_verified=True
                )
                users.append(u)

        from kiboss.apps.common.models import FAQ
        faqs = [
            ('How do I book a ride?', 'Go to Rides, find your route, choose a seat, and complete payment via M-Pesa.', 1),
            ('How do I list an asset?', 'Create a free account, click List an Asset, fill in the details and photos, and submit for verification.', 2),
            ('What payment methods are accepted?', 'We accept M-Pesa, bank transfer, and Lipa Namba. All payments are offline — you pay directly to the owner.', 3),
            ('How long does verification take?', 'Identity verification takes 24–48 hours. Vehicle and asset verification may take up to 3 business days.', 4),
            ('Can I cancel a booking?', 'Yes. Cancellation terms depend on the listing\'s policy. Check the cancellation policy on the listing before booking.', 5),
            ('What is Special Hire?', 'Special hire lets you rent an entire vehicle (HiAce, Coaster, Land Cruiser) for private group use — weddings, funerals, sports trips, and more.', 6),
            ('How does the Business tier work?', 'Business tier gives you unlimited listings, unlimited workers, advanced analytics, and no seat limits on rides. Register at /business/register.', 7),
            ('Is Kiboss available outside Tanzania?', 'Currently, Kiboss operates within Tanzania. We plan to expand to neighbouring countries soon.', 8),
            ('How do I become a verified host?', 'Submit your identity documents through Settings > Verification. Our team reviews within 48 hours.', 9),
            ('What if a booking goes wrong?', 'Use the Report button on any booking. Our support team reviews disputes and assists both parties. Final responsibility rests with users per our Terms.', 10),
        ]
        for question, answer, order in faqs:
            FAQ.objects.get_or_create(
                question=question,
                defaults={'answer': answer, 'order': order, 'is_active': True}
            )

        def get_properties_for_type(atype):
            if atype == AssetType.HOTEL_ROOM:
                return {'room_number': '101', 'floor': 1, 'room_type': 'STANDARD', 'max_adults': 2, 'max_total_occupancy': 2}
            elif atype == AssetType.ENTIRE_HOME:
                return {'bedrooms': 2, 'bathrooms': 1, 'beds': 2, 'square_meters': 100, 'max_guests': 4, 'property_type': 'HOUSE'}
            elif atype == AssetType.VEHICLE:
                return {'vehicle_type': 'VAN', 'make': 'Toyota', 'model': 'Hiace', 'year': 2020, 'seats': 14, 'transmission': 'AUTOMATIC', 'fuel_type': 'DIESEL', 'license_plate': f'T{random.randint(100, 999)}ABC'}
            elif atype == AssetType.RECORDING_STUDIO:
                return {'studio_type': 'AUDIO', 'soundproofing_level': 'PROFESSIONAL', 'max_occupancy': 5, 'hourly_rate': 20000, 'min_hours': 2}
            elif atype == AssetType.CONFERENCE_HALL:
                return {'max_capacity': 100, 'square_meters': 200, 'seating_styles_supported': ['THEATER', 'CLASSROOM']}
            elif atype == AssetType.EVENT_VENUE:
                return {'venue_type': 'INDOOR', 'max_capacity': 200, 'square_meters': 500, 'max_capacity_seated': 150, 'setup_time_minutes': 60, 'teardown_time_minutes': 60}
            elif atype == AssetType.HOT_DESK:
                return {'desk_type': 'OPEN', 'environment_type': 'COWORKING', 'floor': 1}
            elif atype == AssetType.TOOL:
                return {'tool_category': 'CONSTRUCTION', 'power_source': 'ELECTRIC', 'condition': 'GOOD'}
            return {}

        self.stdout.write('Creating assets...')
        assets = []
        for asset_type, names in ASSET_NAMES.items():
            for name in names:
                owner = random.choice(users)
                if 'hassan' in name.lower() or 'amina' in name.lower():
                    owner = users[0] if 'room' in name.lower() else users[3]
                    
                city_data = random.choice(CITIES)
                asset = Asset.objects.create(
                    name=name,
                    asset_type=asset_type,
                    description=f'Beautiful {name} located in {city_data[0]}, perfect for your needs.',
                    address=f'{random.randint(1, 100)} Main St',
                    city=city_data[0],
                    country=city_data[1],
                    latitude=city_data[2],
                    longitude=city_data[3],
                    owner=owner,
                    properties=get_properties_for_type(asset_type),
                    is_listed=True,
                    is_active=True,
                    verification_status=VerificationStatus.VERIFIED if random.random() > 0.3 else VerificationStatus.PENDING,
                    average_rating=round(random.uniform(4.0, 5.0), 1),
                    total_reviews=random.randint(0, 50)
                )
                
                # Pricing
                price = 10000
                unit_type = 'DAY'
                if asset_type == AssetType.HOTEL_ROOM: price = random.randint(5, 20) * 10000
                elif asset_type == AssetType.ENTIRE_HOME: price = random.randint(8, 35) * 10000
                elif asset_type == AssetType.VEHICLE: price = random.randint(8, 20) * 10000
                elif asset_type == AssetType.CONFERENCE_HALL: price = random.randint(10, 50) * 10000
                elif asset_type == AssetType.TOOL: price = random.randint(1, 5) * 10000
                elif asset_type == AssetType.HOT_DESK: price = random.randint(15, 25) * 1000
                
                AssetPricing.objects.create(asset=asset, name='Standard Rate', price=price, unit_type=unit_type, priority=0)
                assets.append(asset)
                
                # Promote some
                if random.random() > 0.8:
                    PromotedListing.objects.create(
                        asset=asset,
                        promotion_type='SPONSORED',
                        starts_at=timezone.now(),
                        ends_at=timezone.now() + timedelta(days=7),
                        is_active=True
                    )

        # Make sure Juma has a verified vehicle
        if not Asset.objects.filter(owner=users[1], asset_type=AssetType.VEHICLE).exists():
            v = Asset.objects.create(
                name='Toyota Hiace (Juma)', asset_type=AssetType.VEHICLE, description='Clean',
                address='Posta', city='Dar es Salaam', country='TZ', owner=users[1],
                properties=get_properties_for_type(AssetType.VEHICLE),
                is_listed=True, is_active=True, verification_status=VerificationStatus.VERIFIED
            )
            AssetPricing.objects.create(asset=v, name='Daily', price=80000, unit_type='DAY', priority=0)
            assets.append(v)

        self.stdout.write('Creating rides...')
        rides = []
        for i in range(20):
            route = random.choice(ROUTES)
            driver = random.choice([u for u in users if u.email in ['juma@example.co.tz', 'hassan@example.co.tz']])
            departure = timezone.now() + timedelta(days=random.randint(1, 7), hours=random.randint(6, 18))
            vehicle = Asset.objects.filter(owner=driver, asset_type=AssetType.VEHICLE).first()
            
            ride = Ride.objects.create(
                route_name=f'{route[0]} to {route[1]}',
                origin=route[0],
                destination=route[1],
                departure_time=departure,
                total_seats=random.randint(4, 14),
                seat_price=random.randint(1, 4) * 10000 + 5000,
                status=RideStatus.OPEN,
                driver=driver,
                vehicle_asset=vehicle,
                currency='TZS'
            )
            # Stops
            RideStop.objects.create(ride=ride, stop_order=1, stop_type='PICKUP', name=route[0], latitude=0, longitude=0)
            RideStop.objects.create(ride=ride, stop_order=2, stop_type='DROPOFF', name=route[1], latitude=0, longitude=0)
            rides.append(ride)

        self.stdout.write('Creating bookings...')
        for i in range(25):
            asset = random.choice(assets)
            renter = random.choice(users)
            if renter == asset.owner: renter = users[2]  # Fatuma
            
            start = timezone.now() + timedelta(days=random.randint(-30, 30))
            end = start + timedelta(days=random.randint(1, 3))
            
            status = random.choice([BookingStatus.COMPLETED, BookingStatus.CONFIRMED, BookingStatus.PENDING, BookingStatus.CANCELLED])
            b = Booking.objects.create(
                renter=renter, asset=asset,
                start_time=start, end_time=end,
                quantity=1, unit_price=asset.pricing_rules.first().price,
                subtotal=asset.pricing_rules.first().price * 2,
                service_fee=0,
                total_price=asset.pricing_rules.first().price * 2,
                currency='TZS', status=status
            )
            
            Payment.objects.create(
                booking=b, amount=b.total_price, currency='TZS',
                payment_method='MPESA', status=PaymentStatus.RELEASED if status == BookingStatus.COMPLETED else PaymentStatus.PENDING
            )
            
            if status == BookingStatus.COMPLETED:
                Rating.objects.create(
                    booking=b, reviewer=renter, reviewee=asset.owner, category=RatingCategory.RENTER_TO_OWNER,
                    overall_rating=random.randint(4, 5), reliability_rating=5, communication_rating=5,
                    title='Great experience', comment='Highly recommended.', status='APPROVED'
                )

        self.stdout.write(self.style.SUCCESS('Successfully populated Tanzanian test data'))
