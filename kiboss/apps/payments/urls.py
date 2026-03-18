"""URL Configuration for Payments API"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from kiboss.apps.payments.views import (
    PaymentViewSet, DisputeViewSet, 
    OfflinePaymentMethodViewSet, SubscriptionPaymentViewSet,
    UserPaymentMethodViewSet, ManualPaymentViewSet
)
from kiboss.apps.payments.zenopay_views import CreateZenoPayOrderView, ZenoPayWebhookView, ZenoPayStatusView

router = DefaultRouter()
router.register(r'disputes', DisputeViewSet, basename='dispute')
router.register(r'offline-methods', OfflinePaymentMethodViewSet, basename='offline-method')
router.register(r'subscription-payments', SubscriptionPaymentViewSet, basename='subscription-payment')
router.register(r'user-payment-methods', UserPaymentMethodViewSet, basename='user-payment-method')
router.register(r'manual-payments', ManualPaymentViewSet, basename='manual-payment')
router.register(r'', PaymentViewSet, basename='payment')

urlpatterns = [
    path('zenopay/create-order/', CreateZenoPayOrderView.as_view(), name='zenopay-create-order'),
    path('zenopay/webhook/', ZenoPayWebhookView.as_view(), name='zenopay-webhook'),
    path('zenopay/status/<str:order_id>/', ZenoPayStatusView.as_view(), name='zenopay-status'),
    path('', include(router.urls)),
]
