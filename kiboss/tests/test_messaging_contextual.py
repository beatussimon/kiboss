import pytest
from django.urls import reverse
from rest_framework import status


@pytest.mark.django_db
class TestContextualMessagingAPI:
    def test_create_contextual_asset_thread_and_reuse(
        self, authenticated_client_second, test_asset, second_user
    ):
        """Contact owner by asset context should create once and then reuse."""
        url = reverse('thread-create-contextual')
        payload = {
            'target_user_id': str(test_asset.owner_id),
            'thread_type': 'INQUIRY',
            'listing_id': str(test_asset.id),
        }

        response = authenticated_client_second.post(url, payload, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['context_type'] == 'ASSET'
        assert response.data['context_id'] == str(test_asset.id)

        second = authenticated_client_second.post(url, payload, format='json')
        assert second.status_code == status.HTTP_200_OK
        assert second.data['id'] == response.data['id']

    def test_create_contextual_requires_exactly_one_context(
        self, authenticated_client_second, test_booking, test_ride, test_user
    ):
        url = reverse('thread-create-contextual')
        payload = {
            'target_user_id': str(test_user.id),
            'thread_type': 'BOOKING',
            'booking_id': str(test_booking.id),
            'ride_id': str(test_ride.id),
        }
        response = authenticated_client_second.post(url, payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['code'] == 'INVALID_CONTEXT'

    def test_create_contextual_disallows_direct_type(
        self, authenticated_client_second, test_asset
    ):
        url = reverse('thread-create-contextual')
        payload = {
            'target_user_id': str(test_asset.owner_id),
            'thread_type': 'DIRECT',
            'listing_id': str(test_asset.id),
        }
        response = authenticated_client_second.post(url, payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['code'] in ['THREAD_TYPE_NOT_ALLOWED', 'INVALID_THREAD_TYPE']

    def test_booking_context_requires_counterparty(
        self, authenticated_client_second, test_booking, test_user
    ):
        """Renter contacting owner on booking succeeds."""
        url = reverse('thread-create-contextual')
        payload = {
            'target_user_id': str(test_user.id),
            'thread_type': 'BOOKING',
            'booking_id': str(test_booking.id),
        }
        response = authenticated_client_second.post(url, payload, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['context_type'] == 'BOOKING'
        assert response.data['context_id'] == str(test_booking.id)

    def test_ride_context_creates_thread(
        self, authenticated_client_second, test_ride, test_user
    ):
        """Passenger contacting driver on ride succeeds."""
        url = reverse('thread-create-contextual')
        payload = {
            'target_user_id': str(test_ride.driver.id),
            'thread_type': 'RIDE',
            'ride_id': str(test_ride.id),
        }
        response = authenticated_client_second.post(url, payload, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['context_type'] == 'RIDE'
        assert response.data['context_id'] == str(test_ride.id)

    def test_ride_context_fails_for_self(
        self, authenticated_client, test_ride
    ):
        """Driver cannot contact themselves about their own ride."""
        url = reverse('thread-create-contextual')
        payload = {
            'target_user_id': str(test_ride.driver.id),
            'thread_type': 'RIDE',
            'ride_id': str(test_ride.id),
        }
        response = authenticated_client.post(url, payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['code'] == 'SELF_CONVERSATION'

    def test_non_context_thread_creation_is_blocked(self, authenticated_client):
        url = reverse('thread-list')
        response = authenticated_client.post(
            url,
            {'thread_type': 'INQUIRY', 'subject': 'Hello'},
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['code'] == 'CONTEXT_REQUIRED'

    def test_read_endpoint_marks_messages_read(
        self, authenticated_client, authenticated_client_second, test_user, second_user, test_asset
    ):
        create_url = reverse('thread-create-contextual')
        create_response = authenticated_client_second.post(
            create_url,
            {
                'target_user_id': str(test_user.id),
                'thread_type': 'INQUIRY',
                'listing_id': str(test_asset.id),
            },
            format='json',
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        thread_id = create_response.data['id']

        send_url = reverse('thread-messages', args=[thread_id])
        send_response = authenticated_client_second.post(
            send_url, {'content': 'Hello'}, format='json'
        )
        assert send_response.status_code == status.HTTP_201_CREATED

        read_url = reverse('thread-read', args=[thread_id])
        read_response = authenticated_client.post(read_url, {}, format='json')
        assert read_response.status_code == status.HTTP_200_OK
        assert read_response.data['status'] == 'ok'
