"""
Property schemas for different AssetTypes in KIBOSS.
Defines required and optional keys for the 'properties' JSON field of the Asset model.
"""
from .models import AssetType

ASSET_SCHEMAS = {
    # --- Accommodation ---
    AssetType.ROOM: {
        'required': ['room_type', 'floor', 'max_guests'],
        'optional': ['amenities', 'natural_light', 'wifi_password', 'bed_configuration', 'has_balcony'],
    },
    AssetType.APARTMENT: {
        'required': ['max_guests', 'bedrooms', 'beds', 'bathrooms'],
        'optional': ['amenities', 'floor', 'furnished', 'parking_included', 'house_rules', 'wifi_password'],
    },
    AssetType.ENTIRE_HOME: {
        'required': ['max_guests', 'bedrooms', 'beds', 'bathrooms'],
        'optional': ['amenities', 'house_rules', 'check_in_instructions', 'wifi_password',
                     'lockbox_code', 'min_nights', 'max_nights', 'cleaning_fee', 'security_deposit'],
    },
    AssetType.PRIVATE_ROOM: {
        'required': ['max_guests', 'bedrooms', 'beds', 'bathrooms'],
        'optional': ['amenities', 'house_rules', 'check_in_instructions', 'wifi_password',
                     'lockbox_code', 'min_nights', 'max_nights', 'cleaning_fee', 'security_deposit'],
    },
    AssetType.SHARED_ROOM: {
        'required': ['max_guests', 'beds'],
        'optional': ['amenities', 'gender_preference', 'locker_included', 'wifi_password', 'house_rules'],
    },
    AssetType.GUEST_HOUSE: {
        'required': ['max_guests', 'bedrooms', 'beds', 'bathrooms'],
        'optional': ['amenities', 'house_rules', 'self_catering', 'pool', 'wifi_password'],
    },
    AssetType.HOTEL_ROOM: {
        'required': ['room_number', 'floor', 'room_type', 'max_adults', 'max_total_occupancy'],
        'optional': ['bed_configuration', 'amenities', 'smoking_allowed', 'housekeeping_status',
                     'check_in_time', 'check_out_time', 'floor_area_sqm', 'has_balcony', 
                     'has_sea_view', 'has_city_view', 'wheelchair_accessible'],
    },

    # --- Venues & Event Spaces ---
    AssetType.EVENT_VENUE: {
        'required': ['max_capacity_seated', 'setup_time_minutes', 'teardown_time_minutes'],
        'optional': ['max_capacity_cocktail', 'max_capacity_standing', 'av_equipment',
                     'in_house_catering', 'parking_spaces', 'outdoor_area', 'rooftop', 
                     'bridal_suite', 'preferred_vendors'],
    },
    AssetType.CONFERENCE_HALL: {
        'required': ['max_capacity_seated', 'floor'],
        'optional': ['av_equipment', 'video_conferencing', 'breakout_rooms', 'max_capacity_standing', 'ac_included'],
    },
    AssetType.BANQUET_HALL: {
        'required': ['max_capacity_seated', 'max_capacity_standing'],
        'optional': ['in_house_catering', 'bar_service', 'dance_floor', 'stage', 'ac_included', 'bridal_suite'],
    },
    AssetType.OUTDOOR_SPACE: {
        'required': ['area_sqm', 'max_capacity'],
        'optional': ['covered', 'power_outlets', 'water_access', 'toilet_facilities', 'parking_available'],
    },
    AssetType.ROOFTOP: {
        'required': ['area_sqm', 'max_capacity'],
        'optional': ['covered', 'elevator_access', 'view_type', 'bar_available', 'toilet_facilities'],
    },
    AssetType.PRIVATE_DINING_ROOM: {
        'required': ['max_capacity_seated'],
        'optional': ['in_house_catering', 'av_equipment', 'private_bar', 'ac_included'],
    },
    AssetType.DINING_TABLE: {
        'required': ['seats', 'location_in_venue'],
        'optional': ['window_seat', 'outdoor', 'private'],
    },

    # --- Workspaces ---
    AssetType.OFFICE_SPACE: {
        'required': ['area_sqm', 'max_capacity'],
        'optional': ['furnished', 'internet_speed_mbps', 'meeting_rooms_included', 'printer_access', 'reception_service', '24h_access'],
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

    # --- Studios ---
    AssetType.RECORDING_STUDIO: {
        'required': ['studio_type', 'min_hours'],
        'optional': ['equipment_list', 'engineer_included', 'engineer_rate', 'mixing_rate',
                     'mastering_rate', 'live_room_size', 'control_room_seats', 
                     'soundproofing_rating', 'amenities', 'hourly_rate'],
    },
    AssetType.PHOTO_STUDIO: {
        'required': ['studio_type', 'area_sqm'],
        'optional': ['backdrops', 'lighting_included', 'equipment_list', 'changing_room', 'makeup_station', 'min_hours'],
    },
    AssetType.DANCE_STUDIO: {
        'required': ['area_sqm', 'max_capacity'],
        'optional': ['mirrors', 'sound_system', 'sprung_floor', 'changing_rooms', 'barres'],
    },
    AssetType.PODCAST_STUDIO: {
        'required': ['max_hosts', 'min_hours'],
        'optional': ['equipment_list', 'soundproofing_rating', 'video_capable', 'live_streaming'],
    },
    AssetType.ART_STUDIO: {
        'required': ['area_sqm'],
        'optional': ['natural_light', 'sink_available', 'storage_included', 'kiln_access', 'easels'],
    },

    # --- Vehicles & Transport ---
    AssetType.VEHICLE: {
        'required': ['license_plate', 'make', 'model', 'year', 'vehicle_type'],
        'optional': ['color', 'transmission', 'fuel_type', 'engine_size', 'mileage', 
                     'ac', 'wheelchair_accessible', 'seat_capacity', 'cargo_capacity_kg'],
    },
    AssetType.BOAT: {
        'required': ['boat_type', 'length_ft', 'max_passengers'],
        'optional': ['captain_included', 'fuel_included', 'fishing_gear', 'engine_type', 'year', 'registration_number'],
    },
    AssetType.BICYCLE: {
        'required': ['bike_type', 'frame_size'],
        'optional': ['gears', 'electric', 'lock_included', 'helmet_included', 'basket', 'brand'],
    },
    AssetType.TOW_TRUCK: {
        'required': ['license_plate', 'make', 'model', 'year', 'tow_capacity_kg'],
        'optional': ['color', 'tow_type', 'has_winch', 'has_flatbed', 'equipment_list', 'is_heavy_duty'],
    },

    # --- Storage & Parking ---
    AssetType.PARKING_SPACE: {
        'required': ['space_type', 'vehicle_size'],
        'optional': ['covered', 'security', 'ev_charging', '24h_access', 'floor'],
    },
    AssetType.STORAGE_UNIT: {
        'required': ['size_sqm', 'access_type'],
        'optional': ['climate_controlled', 'security_level', 'ground_floor', '24h_access'],
    },

    # --- Equipment ---
    AssetType.TOOL: {
        'required': ['tool_type', 'condition'],
        'optional': ['brand', 'model', 'power_source', 'safety_gear_required', 'delivery_available'],
    },
    AssetType.SPORTS_EQUIPMENT: {
        'required': ['equipment_type', 'condition'],
        'optional': ['brand', 'size', 'includes_accessories', 'delivery_available'],
    },
    AssetType.GENERATOR: {
        'required': ['power_kva', 'fuel_type'],
        'optional': ['brand', 'noise_level_db', 'portable', 'delivery_available', 'operator_included'],
    },
    AssetType.MUSICAL_INSTRUMENT: {
        'required': ['instrument_type', 'condition'],
        'optional': ['brand', 'model', 'includes_case', 'includes_accessories', 'amplifier_included'],
    },
    AssetType.CAMERA_EQUIPMENT: {
        'required': ['equipment_type', 'brand', 'model'],
        'optional': ['condition', 'includes_lenses', 'includes_tripod', 'includes_lighting', 'memory_cards'],
    },

    # --- Corporate Properties ---
    AssetType.HOTEL: {
        'required': ['star_rating', 'total_rooms'],
        'optional': ['amenities', 'check_in_time', 'check_out_time', 'pool', 'gym', 'restaurant', 'parking'],
    },
    AssetType.RESTAURANT: {
        'required': ['cuisine_type', 'total_tables'],
        'optional': ['outdoor_seating', 'bar', 'private_dining', 'delivery', 'takeaway'],
    },

    # --- Service Types ---
    AssetType.TIME_SERVICE: {
        'required': ['service_type', 'duration_minutes'],
        'optional': ['provider_qualifications', 'location_type', 'equipment_provided'],
    },
}
