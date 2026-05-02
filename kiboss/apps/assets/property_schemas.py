"""
Property schemas for different AssetTypes in KIBOSS.
Defines required and optional keys for the 'properties' JSON field of the Asset model.
"""
from .models import AssetType

ASSET_SCHEMAS = {
    AssetType.HOTEL_ROOM: {
        'required': ['room_number', 'floor', 'room_type', 'max_adults', 'max_total_occupancy'],
        'optional': ['bed_configuration', 'amenities', 'smoking_allowed', 'housekeeping_status',
                     'check_in_time', 'check_out_time', 'floor_area_sqm', 'has_balcony', 
                     'has_sea_view', 'has_city_view', 'wheelchair_accessible'],
    },
    AssetType.EVENT_VENUE: {
        'required': ['max_capacity_seated', 'setup_time_minutes', 'teardown_time_minutes'],
        'optional': ['max_capacity_cocktail', 'max_capacity_standing', 'av_equipment',
                     'in_house_catering', 'parking_spaces', 'outdoor_area', 'rooftop', 
                     'bridal_suite', 'preferred_vendors'],
    },
    AssetType.VEHICLE: {
        'required': ['license_plate', 'make', 'model', 'year', 'vehicle_type'],
        'optional': ['color', 'transmission', 'fuel_type', 'engine_size', 'mileage', 
                     'ac', 'wheelchair_accessible', 'seat_capacity', 'cargo_capacity_kg'],
    },
    AssetType.RECORDING_STUDIO: {
        'required': ['studio_type', 'hourly_rate', 'min_hours'],
        'optional': ['equipment_list', 'engineer_included', 'engineer_rate', 'mixing_rate',
                     'mastering_rate', 'live_room_size', 'control_room_seats', 
                     'soundproofing_rating', 'amenities'],
    },
    AssetType.HOT_DESK: {
        'required': ['desk_type', 'floor'],
        'optional': ['natural_light', 'standing_desk', 'locker_included', 'amenities',
                     'internet_speed_mbps', 'printer_included', 'kitchen_access', 
                     'reception_service'],
    },
    AssetType.MEETING_ROOM: {
        'required': ['max_capacity', 'floor'],
        'optional': ['av_equipment', 'whiteboard', 'video_conferencing', 'amenities'],
    },
    AssetType.PRIVATE_ROOM: {
        'required': ['max_guests', 'bedrooms', 'beds', 'bathrooms'],
        'optional': ['amenities', 'house_rules', 'check_in_instructions', 'wifi_password',
                     'lockbox_code', 'min_nights', 'max_nights', 'cleaning_fee', 'security_deposit'],
    },
    AssetType.ENTIRE_HOME: {
        'required': ['max_guests', 'bedrooms', 'beds', 'bathrooms'],
        'optional': ['amenities', 'house_rules', 'check_in_instructions', 'wifi_password',
                     'lockbox_code', 'min_nights', 'max_nights', 'cleaning_fee', 'security_deposit'],
    },
}

# Add fallbacks for other types if needed, or leave empty to skip validation
