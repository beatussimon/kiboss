from django.contrib import admin
from .models import (
    Asset, AssetPhoto, AssetDocument, AssetPricing, AssetAvailability,
    AssetCapacity, AssetTimeGranularity, AssetJurisdiction, AssetLike
)

class AssetPhotoInline(admin.TabularInline):
    model = AssetPhoto
    extra = 1

class AssetDocumentInline(admin.TabularInline):
    model = AssetDocument
    extra = 1

class AssetPricingInline(admin.TabularInline):
    model = AssetPricing
    extra = 0

class AssetCapacityInline(admin.TabularInline):
    model = AssetCapacity
    extra = 0

@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ('name', 'asset_type', 'owner', 'city', 'country', 'verification_status', 'is_active', 'is_listed')
    list_filter = ('asset_type', 'verification_status', 'is_active', 'is_listed', 'country')
    search_fields = ('name', 'description', 'owner__email', 'city')
    inlines = [AssetPhotoInline, AssetDocumentInline, AssetPricingInline, AssetCapacityInline]
    readonly_fields = ('created_at', 'updated_at', 'verified_at', 'verified_by')

@admin.register(AssetPhoto)
class AssetPhotoAdmin(admin.ModelAdmin):
    list_display = ('asset', 'caption', 'order', 'is_primary')
    list_filter = ('is_primary',)
    search_fields = ('asset__name', 'caption')

@admin.register(AssetDocument)
class AssetDocumentAdmin(admin.ModelAdmin):
    list_display = ('asset', 'document_type', 'name', 'is_verified', 'expiry_date')
    list_filter = ('document_type', 'is_verified')
    search_fields = ('asset__name', 'name')

@admin.register(AssetPricing)
class AssetPricingAdmin(admin.ModelAdmin):
    list_display = ('asset', 'name', 'unit_type', 'price', 'is_active', 'priority')
    list_filter = ('unit_type', 'is_active')
    search_fields = ('asset__name', 'name')

@admin.register(AssetAvailability)
class AssetAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('asset', 'name', 'availability_type', 'is_active')
    list_filter = ('availability_type', 'is_active')
    search_fields = ('asset__name', 'name')

@admin.register(AssetCapacity)
class AssetCapacityAdmin(admin.ModelAdmin):
    list_display = ('asset', 'capacity_type', 'quantity', 'description')
    list_filter = ('capacity_type',)
    search_fields = ('asset__name', 'description')

@admin.register(AssetTimeGranularity)
class AssetTimeGranularityAdmin(admin.ModelAdmin):
    list_display = ('asset', 'min_duration_minutes', 'increment_minutes', 'any_start_time')
    search_fields = ('asset__name',)

@admin.register(AssetJurisdiction)
class AssetJurisdictionAdmin(admin.ModelAdmin):
    list_display = ('asset', 'country', 'state', 'city', 'license_required', 'insurance_required')
    list_filter = ('country', 'license_required', 'insurance_required')
    search_fields = ('asset__name', 'country', 'state', 'city')

@admin.register(AssetLike)
class AssetLikeAdmin(admin.ModelAdmin):
    list_display = ('asset', 'user', 'created_at')
    search_fields = ('asset__name', 'user__email')
    readonly_fields = ('created_at',)
