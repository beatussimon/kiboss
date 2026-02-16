"""
URL Configuration for Messaging API
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from kiboss.apps.messaging.views import ThreadViewSet, MessageViewSet, AttachmentViewSet

router = DefaultRouter()
router.register(r'threads', ThreadViewSet, basename='thread')
router.register(r'messages', MessageViewSet, basename='message')
router.register(r'attachments', AttachmentViewSet, basename='attachment')

urlpatterns = [
    path('', include(router.urls)),
]
