import pytest
from django.urls import reverse
from rest_framework import status
from kiboss.apps.common.models import Feedback

@pytest.mark.django_db
class TestFeedbackResolution:
    def test_staff_can_resolve_feedback(self, admin_client, test_user):
        # Create a feedback
        feedback = Feedback.objects.create(
            user=test_user,
            subject="Test Subject",
            message="Test Message",
            category=Feedback.Category.TECHNICAL
        )
        assert not feedback.is_resolved

        url = reverse('feedback-detail', kwargs={'pk': feedback.id})
        response = admin_client.patch(url, {'is_resolved': True}, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        feedback.refresh_from_db()
        assert feedback.is_resolved
        assert response.data['is_resolved'] is True

    def test_user_cannot_resolve_own_feedback(self, authenticated_client, test_user):
        # Create a feedback
        feedback = Feedback.objects.create(
            user=test_user,
            subject="Test Subject",
            message="Test Message",
            category=Feedback.Category.TECHNICAL
        )
        assert not feedback.is_resolved

        url = reverse('feedback-detail', kwargs={'pk': feedback.id})
        response = authenticated_client.patch(url, {'is_resolved': True}, format='json')
        
        # Should fail validation or ignore if we used the logic I added
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Only staff can change the resolution status." in str(response.data)
        feedback.refresh_from_db()
        assert not feedback.is_resolved

    def test_user_cannot_resolve_other_user_feedback(self, authenticated_client, second_user):
        # Create a feedback for second_user
        feedback = Feedback.objects.create(
            user=second_user,
            subject="Test Subject",
            message="Test Message",
            category=Feedback.Category.TECHNICAL
        )
        
        # test_user tries to access second_user's feedback
        url = reverse('feedback-detail', kwargs={'pk': feedback.id})
        response = authenticated_client.patch(url, {'is_resolved': True}, format='json')
        
        # Should be 404 because get_queryset filters by user
        assert response.status_code == status.HTTP_404_NOT_FOUND
