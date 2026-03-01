"""
Tier Service for KIBOSS - Business Tiers Feature Definitions

Defines what each tier gets:
- FREE: Basic listing, no boosts, standard visibility
- PLUS: 3 boosts/month, 1.5x visibility, priority support badge, analytics preview
- BUSINESS: Unlimited boosts, 2.0x visibility, full analytics, fleet management,
            worker management, support inbox, verified badge, priority listings
"""

from django.conf import settings


TIER_FEATURES = {
    'FREE': {
        'name': 'Free',
        'price_monthly_tzs': 0,
        'price_yearly_tzs': 0,
        'max_listings': 5,
        'max_boosts_per_month': 0,
        'visibility_multiplier': 1.0,
        'analytics_access': False,
        'fleet_management': False,
        'worker_management': False,
        'support_inbox': False,
        'priority_support': False,
        'verified_badge': False,
        'custom_branding': False,
        'highlights': [
            'Up to 5 listings',
            'Standard visibility',
            'Basic messaging',
            'Community support',
        ],
    },
    'PLUS': {
        'name': 'Plus',
        'price_monthly_tzs': 15000,
        'price_yearly_tzs': 150000,
        'max_listings': 25,
        'max_boosts_per_month': 3,
        'visibility_multiplier': 1.5,
        'analytics_access': True,
        'fleet_management': False,
        'worker_management': False,
        'support_inbox': False,
        'priority_support': True,
        'verified_badge': True,
        'custom_branding': False,
        'highlights': [
            'Up to 25 listings',
            '3 boosts per month',
            '1.5x visibility boost',
            'Analytics preview',
            'Priority support badge',
            'Plus verification badge',
        ],
    },
    'BUSINESS': {
        'name': 'Business',
        'price_monthly_tzs': 50000,
        'price_yearly_tzs': 500000,
        'max_listings': -1,  # unlimited
        'max_boosts_per_month': -1,  # unlimited
        'visibility_multiplier': 2.0,
        'analytics_access': True,
        'fleet_management': True,
        'worker_management': True,
        'support_inbox': True,
        'priority_support': True,
        'verified_badge': True,
        'custom_branding': True,
        'highlights': [
            'Unlimited listings',
            'Unlimited boosts',
            '2.0x visibility boost',
            'Full analytics dashboard',
            'Fleet management',
            'Worker management',
            'Support inbox',
            'Custom branding',
            'Business verification badge',
        ],
    },
}


def get_tier_features(tier: str) -> dict:
    """Get feature dictionary for a tier."""
    return TIER_FEATURES.get(tier, TIER_FEATURES['FREE'])


def can_user_access_feature(user, feature: str) -> bool:
    """Check if a user's tier allows access to a specific feature."""
    tier = getattr(user, 'account_tier', 'FREE')
    features = get_tier_features(tier)
    return features.get(feature, False)


def get_all_tiers() -> list:
    """Get all tier definitions for the upgrade comparison page."""
    return [
        {'tier_id': key, **value}
        for key, value in TIER_FEATURES.items()
    ]
