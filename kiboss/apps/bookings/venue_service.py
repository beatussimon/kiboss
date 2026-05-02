"""
Venue Booking Service for KIBOSS
"""

import logging
from decimal import Decimal
from django.utils import timezone
from kiboss.apps.bookings.services import BookingService, BookingError

logger = logging.getLogger(__name__)

class VenueBookingService:
    """
    Service for handling venue bookings.
    Handles setup/teardown buffers, capacity, and add-ons.
    """
    
    @classmethod
    def create_venue_booking(cls, renter, asset, start_time, end_time, quantity, venue_data):
        """
        Create a venue booking.
        """
        setup_hours = venue_data.get('setup_time_hours', 2)
        teardown_hours = venue_data.get('teardown_time_hours', 1)
        headcount = venue_data.get('headcount', 1)
        add_ons = venue_data.get('add_ons', [])
        
        # Adjust start/end times with buffers for availability check
        # The user's event is from start_time to end_time, but the venue is blocked longer.
        # However, for the Booking model, we might want to store the actual event time
        # and use metadata for buffers.
        
        # Check capacity
        venue_capacity = asset.get_property('capacity', 0)
        if headcount > venue_capacity:
            raise BookingError(f"Headcount {headcount} exceeds venue capacity {venue_capacity}")
        
        # Calculate price
        price_breakdown = BookingService.calculate_price(
            asset.id, quantity, start_time, end_time
        )
        
        # Add cost for add-ons (simplified)
        add_on_cost = Decimal('0.00')
        for add_on in add_ons:
            add_on_cost += Decimal('50000.00') # Fixed price per add-on for now
            
        price_breakdown['base_price'] += add_on_cost
        price_breakdown['subtotal'] += add_on_cost
        price_breakdown['service_fee'] = price_breakdown['subtotal'] * Decimal('0.10')
        tax_rate = Decimal(str(price_breakdown.get('tax_rate', '0.00')))
        price_breakdown['taxes'] = (price_breakdown['subtotal'] + price_breakdown['service_fee']) * tax_rate
        price_breakdown['total'] = price_breakdown['subtotal'] + price_breakdown['service_fee'] + price_breakdown['taxes']
        
        price_breakdown['venue_details'] = {
            'setup_time_hours': setup_hours,
            'teardown_time_hours': teardown_hours,
            'headcount': headcount,
            'add_ons': add_ons,
            'add_on_cost': str(add_on_cost)
        }
        
        return BookingService.create_booking(
            renter=renter,
            asset_id=asset.id,
            start_time=start_time,
            end_time=end_time,
            quantity=quantity,
            notes=venue_data.get('notes', ''),
        )
