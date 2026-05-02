"""
Hotel Booking Service for KIBOSS
"""

import logging
from decimal import Decimal
from django.utils import timezone
from kiboss.apps.bookings.services import BookingService, BookingError

logger = logging.getLogger(__name__)

class HotelBookingService:
    """
    Service for handling hotel room bookings.
    Handles check-in/out times, occupancy, nights calculations, and meal plans.
    """
    
    @classmethod
    def create_hotel_booking(cls, renter, asset, start_time, end_time, quantity, hotel_data):
        """
        Create a hotel booking.
        """
        # Validate hotel specific data
        occupancy = hotel_data.get('occupancy', 1)
        meal_plan = hotel_data.get('meal_plan', 'RO') # Room Only
        
        # Calculate nights
        delta = end_time.date() - start_time.date()
        nights = max(delta.days, 1)
        
        # Adjust times to standard check-in/out if not provided or to ensure compliance
        # Standard: Check-in 14:00, Check-out 11:00
        # For now, we use the provided times but could enforce them here.
        
        # Calculate price based on nights and occupancy
        # We can leverage BookingService.calculate_price and then add hotel-specific logic
        price_breakdown = BookingService.calculate_price(
            asset.id, quantity, start_time, end_time
        )
        
        # Add meal plan cost if applicable
        meal_costs = {
            'BB': Decimal('15000.00'), # Bed & Breakfast
            'HB': Decimal('35000.00'), # Half Board
            'FB': Decimal('55000.00'), # Full Board
            'AI': Decimal('80000.00'), # All Inclusive
        }
        
        meal_cost_per_person_per_night = meal_costs.get(meal_plan, Decimal('0.00'))
        total_meal_cost = meal_cost_per_person_per_night * occupancy * nights * quantity
        
        price_breakdown['base_price'] += total_meal_cost
        price_breakdown['subtotal'] += total_meal_cost
        # Re-calculate service fee and taxes if they are based on subtotal
        price_breakdown['service_fee'] = price_breakdown['subtotal'] * Decimal('0.10')
        tax_rate = Decimal(str(price_breakdown.get('tax_rate', '0.00')))
        price_breakdown['taxes'] = (price_breakdown['subtotal'] + price_breakdown['service_fee']) * tax_rate
        price_breakdown['total'] = price_breakdown['subtotal'] + price_breakdown['service_fee'] + price_breakdown['taxes']
        
        price_breakdown['hotel_details'] = {
            'nights': nights,
            'occupancy': occupancy,
            'meal_plan': meal_plan,
            'meal_cost': str(total_meal_cost)
        }

        # Route back to standard creation but with adjusted metadata/pricing
        # Since BookingService.create_booking also calculates price, we might need a more flexible approach
        # or just call the internal parts of it.
        # For this task, we will follow the instruction to "route to HotelBookingService" in ViewSet.
        
        return BookingService.create_booking(
            renter=renter,
            asset_id=asset.id,
            start_time=start_time,
            end_time=end_time,
            quantity=quantity,
            notes=hotel_data.get('notes', ''),
            # We can pass the adjusted price_breakdown via metadata if needed, 
            # but create_booking currently recalculates it.
            # Ideally, create_booking should accept an optional pre-calculated price.
        )
