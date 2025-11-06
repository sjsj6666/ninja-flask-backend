# test_app.py

import pytest
import json
from app import app
from unittest.mock import patch, MagicMock

# This creates a 'test client' that lets us simulate web requests to our app without running a live server.
@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

# --- Test Cases ---

def test_health_check(client):
    """Tests if the /health endpoint is working and returns a success status."""
    response = client.get('/health')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'healthy'

def test_game_validation_success(client):
    """Tests a successful game validation call, mocking the external API."""
    # We use @patch to 'intercept' the call to perform_ml_check.
    # Instead of making a real network request, it will just return our predefined success data.
    with patch('app.perform_ml_check') as mock_ml_check:
        mock_ml_check.return_value = {
            'status': 'success', 
            'username': 'TestPlayer',
            'region': 'SG'
        }
        
        response = client.get('/check-id/mobile-legends/12345/5001')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'success'
        assert data['username'] == 'TestPlayer'

def test_validation_with_missing_user_id(client):
    """Tests that the API correctly returns an error if the User ID is missing."""
    # We expect this to fail, so we don't need to patch anything.
    response = client.get('/check-id/mobile-legends//5001') # Note the empty UID
    assert response.status_code == 404 # Flask returns 404 for missing URL parts

def test_validation_for_unsupported_game(client):
    """Tests that the API returns an error for a game that is not configured."""
    response = client.get('/check-id/unsupported-game/12345')
    assert response.status_code == 400 # We expect a Validation Error
    data = json.loads(response.data)
    assert data['status'] == 'error'
    assert data['error_code'] == 'VALIDATION_ERROR'

def test_qr_generation_success(client):
    """Tests a successful QR code generation, mocking the external Maybank API."""
    with patch('app.requests.get') as mock_requests_get:
        # Create a fake successful response from the Maybank API
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Type': 'image/png'}
        mock_response.content = b'fake_qr_image_bytes'
        mock_requests_get.return_value = mock_response
        
        response = client.post('/create-paynow-qr', json={
            'amount': 10.99,
            'order_id': 'a1b2c3d4-e5f6-7890-1234-567890abcdef'
        })
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'qr_code_data' in data
        assert 'expiry_timestamp' in data

def test_qr_generation_missing_data(client):
    """Tests that the QR code endpoint fails if 'amount' or 'order_id' is missing."""
    response = client.post('/create-paynow-qr', json={'amount': 10.99}) # Missing order_id
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error_code'] == 'VALIDATION_ERROR'
