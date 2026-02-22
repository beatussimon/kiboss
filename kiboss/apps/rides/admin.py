from django.contrib import admin
from .models import Ride, RideStop, SeatBooking, RideSchedule, RidePhoto

@admin.register(Ride)
class RideAdmin(admin.ModelAdmin):
    list_display = ('id', 'driver', 'origin', 'destination', 'departure_time', 'status', 'total_seats', 'available_seats')
    list_filter = ('status', 'departure_time', 'is_recurring')
    search_fields = ('origin', 'destination', 'driver__email', 'route_name')
    readonly_fields = ('created_at', 'updated_at')
    
    def available_seats(self, obj):
        return obj.get_available_seats()

@admin.register(RideStop)
class RideStopAdmin(admin.ModelAdmin):
    list_display = ('ride', 'name', 'stop_type', 'stop_order', 'estimated_arrival')
    list_filter = ('stop_type',)
    search_fields = ('name', 'address', 'ride__origin', 'ride__destination')

@admin.register(SeatBooking)
class SeatBookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'ride', 'passenger', 'seat_number', 'status', 'price')
    list_filter = ('status', 'created_at')
    search_fields = ('passenger__email', 'ride__origin', 'ride__destination')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(RideSchedule)
class RideScheduleAdmin(admin.ModelAdmin):
    list_display = ('name', 'driver', 'schedule_type', 'origin', 'destination', 'active_status')
    list_filter = ('schedule_type', 'is_active')
    search_fields = ('name', 'driver__email', 'origin', 'destination')
    
    def active_status(self, obj):
        return obj.is_active
    active_status.boolean = True

@admin.register(RidePhoto)
class RidePhotoAdmin(admin.ModelAdmin):
    list_display = ('ride', 'caption', 'order', 'is_primary')
    list_filter = ('is_primary',)
