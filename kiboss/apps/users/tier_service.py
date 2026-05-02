"""
Tier Service for KIBOSS - Business Tiers Feature Definitions

Defines what each tier gets, potentially scoped by business category.
- FREE: Basic listing, no boosts, standard visibility
- PLUS: 3 boosts/month, 1.5x visibility, priority support badge, analytics preview
- BUSINESS: Unlimited boosts, 2.0x visibility, full analytics, fleet management,
            worker management, support inbox, verified badge, priority listings
"""

from django.conf import settings
from rest_framework.permissions import BasePermission


TIER_FEATURES = {
    'FREE': {
        'ALL': {
            'max_listings': 3,
            'max_photos_per_listing': 5,
            'can_boost': False,
            'analytics_basic': True,
            'analytics_advanced': False,
            'worker_accounts': 0,
            'custom_cancellation_policy': False,
            'offline_payment_methods': 1,
            'api_access': False,
        }
    },
    'PLUS': {
        'ALL': {
            'max_listings': 25,
            'max_photos_per_listing': 20,
            'boosts_per_month': 3,
            'analytics_basic': True,
            'analytics_advanced': False,
            'worker_accounts': 2,
            'custom_cancellation_policy': True,
            'offline_payment_methods': 5,
            'api_access': False,
        },
        'HOSPITALITY': {
            'max_listings': -1,  # unlimited rooms under one property
            'housekeeping_module': True,
            'occupancy_reports': True,
        },
        'HOME_SHARING': {
            'instant_book': True,
            'co_host': True,
        }
    },
    'BUSINESS': {
        'ALL': {
            'max_listings': -1,
            'max_photos_per_listing': -1,
            'boosts_per_month': -1,
            'analytics_basic': True,
            'analytics_advanced': True,
            'worker_accounts': -1,
            'custom_cancellation_policy': True,
            'offline_payment_methods': -1,
            'api_access': True,
            'custom_branding': True,
            'priority_support': True,
            'revenue_reports': True,
            'export_data': True,
        },
        'HOSPITALITY': {
            'front_desk_mode': True,
            'housekeeping_module': True,
            'channel_manager_ready': True,  # future integration
            'occupancy_revpar_adr': True,
            'multi_property': True,
        },
        'VENUE': {
            'event_calendar': True,
            'quote_builder': True,
            'site_visit_scheduler': True,
        },
        'STUDIO': {
            'session_log': True,
            'client_portal': True,
        },
        'COWORKING': {
            'member_management': True,
            'monthly_invoice_generation': True,
            'access_control_integration_ready': True,
        },
    }
}


def get_tier_features(tier: str) -> dict:
    """Get feature dictionary for a tier."""
    return TIER_FEATURES.get(tier, TIER_FEATURES['FREE'])


def can_user_access_feature(user, feature: str, category: str = 'ALL') -> bool:
    """Check if a user's tier allows access to a specific feature."""
    tier = getattr(user, 'account_tier', 'FREE')
    tier_data = get_tier_features(tier)
    
    # Check category specific features first
    if category != 'ALL' and category in tier_data:
        if feature in tier_data[category]:
            return tier_data[category][feature]
            
    # Fallback to ALL features
    return tier_data.get('ALL', {}).get(feature, False)


def get_all_tiers() -> list:
    """Get all tier definitions for the upgrade comparison page."""
    return [
        {'tier_id': key, **value}
        for key, value in TIER_FEATURES.items()
    ]


class RequiresTier(BasePermission):
    """
    DRF permission class to enforce tier requirements.
    Usage: permission_classes = [IsAuthenticated, RequiresTier('PLUS')]
    """
    def __init__(self, min_tier: str, feature: str = None):
        self.min_tier = min_tier
        self.feature = feature
    
    def has_permission(self, request, view):
        tier_order = ['FREE', 'PLUS', 'BUSINESS']
        
        # Handle cases where user is not authenticated or lacks attribute
        user_tier = getattr(request.user, 'account_tier', 'FREE')
        if user_tier not in tier_order:
            user_tier = 'FREE'
            
        user_tier_idx = tier_order.index(user_tier)
        required_idx = tier_order.index(self.min_tier)
        
        if user_tier_idx < required_idx:
            return False
            
        if self.feature:
            # We don't have category here easily, default to ALL
            return can_user_access_feature(request.user, self.feature)
            
        return True
