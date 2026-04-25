import pytest
import requests
import json

def test_create_booking_happy_path():
    url = 'https://restful-booker.herokuapp.com/booking'
    headers = {'Content-Type': 'application/json'}
    payload = {
        'firstname': 'Jim',
        'lastname': 'Brown',
        'totalprice': 111,
        'depositpaid': True,
        'bookingdates': {
            'checkin': '2024-01-01',
            'checkout': '2024-01-10'
        },
        'additionalneeds': 'Breakfast'
    }
    
    response = requests.post(url, headers=headers, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert 'bookingid' in data
    assert isinstance(data['bookingid'], int)
    assert data['booking'] == payload

import pytest
import requests
import json

@pytest.mark.parametrize('payload,expected_status', [
    ({'lastname': 'Brown', 'totalprice': 111, 'depositpaid': True, 'bookingdates': {'checkin': '2024-01-01', 'checkout': '2024-01-10'}, 'additionalneeds': 'Breakfast'}, 500),
    ({'firstname': 'Jim', 'totalprice': 111, 'depositpaid': True, 'bookingdates': {'checkin': '2024-01-01', 'checkout': '2024-01-10'}, 'additionalneeds': 'Breakfast'}, 500),
    ({'firstname': 'Jim', 'lastname': 'Brown', 'depositpaid': True, 'bookingdates': {'checkin': '2024-01-01', 'checkout': '2024-01-10'}, 'additionalneeds': 'Breakfast'}, 500),
    ({'firstname': 'Jim', 'lastname': 'Brown', 'totalprice': 111, 'bookingdates': {'checkin': '2024-01-01', 'checkout': '2024-01-10'}, 'additionalneeds': 'Breakfast'}, 500),
])
def test_create_booking_missing_required_field(payload, expected_status):
    url = 'https://restful-booker.herokuapp.com/booking'
    headers = {'Content-Type': 'application/json'}
    
    response = requests.post(url, headers=headers, json=payload)
    assert response.status_code == expected_status

import pytest
import requests
import json

@pytest.fixture(scope='function')
def created_booking_id():
    url = 'https://restful-booker.herokuapp.com/booking'
    headers = {'Content-Type': 'application/json'}
    payload = {
        'firstname': 'Test',
        'lastname': 'User',
        'totalprice': 100,
        'depositpaid': False,
        'bookingdates': {
            'checkin': '2024-01-01',
            'checkout': '2024-01-02'
        },
        'additionalneeds': 'WiFi'
    }
    response = requests.post(url, headers=headers, json=payload)
    assert response.status_code == 200
    booking_id = response.json()['bookingid']
    yield booking_id
    # Teardown: delete if exists (ignore failure)
    try:
        delete_url = f'https://restful-booker.herokuapp.com/booking/{booking_id}'
        auth = ('admin', 'password123')
        requests.delete(delete_url, auth=auth)
    except:
        pass

def test_get_booking_exists(created_booking_id):
    url = f'https://restful-booker.herokuapp.com/booking/{created_booking_id}'
    headers = {'Accept': 'application/json'}
    
    response = requests.get(url, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data['bookingid'] == created_booking_id

import pytest
import requests

def test_get_booking_not_exists():
    # Use an obviously invalid ID
    url = 'https://restful-booker.herokuapp.com/booking/999999999'
    headers = {'Accept': 'application/json'}
    
    response = requests.get(url, headers=headers)
    assert response.status_code == 404

import pytest
import requests

@pytest.fixture(scope='function')
def created_booking_id():
    url = 'https://restful-booker.herokuapp.com/booking'
    headers = {'Content-Type': 'application/json'}
    payload = {
        'firstname': 'DelTest',
        'lastname': 'User',
        'totalprice': 200,
        'depositpaid': True,
        'bookingdates': {
            'checkin': '2024-01-01',
            'checkout': '2024-01-03'
        },
        'additionalneeds': 'Lunch'
    }
    response = requests.post(url, headers=headers, json=payload)
    assert response.status_code == 200
    booking_id = response.json()['bookingid']
    yield booking_id
    # cleanup ignored on purpose for unauthorized test

def test_delete_booking_unauthorized(created_booking_id):
    url = f'https://restful-booker.herokuapp.com/booking/{created_booking_id}'
    headers = {'Content-Type': 'application/json'}
    
    response = requests.delete(url, headers=headers)
    assert response.status_code == 401

import pytest
import requests

@pytest.fixture(scope='function')
def created_booking_id():
    url = 'https://restful-booker.herokuapp.com/booking'
    headers = {'Content-Type': 'application/json'}
    payload = {
        'firstname': 'AuthDel',
        'lastname': 'Test',
        'totalprice': 300,
        'depositpaid': True,
        'bookingdates': {
            'checkin': '2024-01-05',
            'checkout': '2024-01-07'
        },
        'additionalneeds': 'Parking'
    }
    response = requests.post(url, headers=headers, json=payload)
    assert response.status_code == 200
    booking_id = response.json()['bookingid']
    yield booking_id

def test_delete_booking_authorized_success(created_booking_id):
    url = f'https://restful-booker.herokuapp.com/booking/{created_booking_id}'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Basic YWRtaW46cGFzc3dvcmQxMjM='
    }
    
    response = requests.delete(url, headers=headers)
    assert response.status_code == 201
    
    # Verify deletion via GET
    get_url = f'https://restful-booker.herokuapp.com/booking/{created_booking_id}'
    get_headers = {'Accept': 'application/json'}
    get_response = requests.get(get_url, headers=get_headers)
    assert get_response.status_code == 404