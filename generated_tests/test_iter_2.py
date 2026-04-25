import pytest
import requests
import json

def test_create_booking_happy_path():
    url = "https://restful-booker.herokuapp.com/booking"
    headers = {"Content-Type": "application/json"}
    payload = {
        "firstname": "Jim",
        "lastname": "Brown",
        "totalprice": 111,
        "depositpaid": True,
        "bookingdates": {
            "checkin": "2024-01-01",
            "checkout": "2024-01-10"
        },
        "additionalneeds": "Breakfast"
    }

    response = requests.post(url, headers=headers, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "bookingid" in data
    assert isinstance(data["bookingid"], int)
    assert data["booking"] is not None

import pytest
import requests

def test_create_booking_missing_firstname():
    url = "https://restful-booker.herokuapp.com/booking"
    headers = {"Content-Type": "application/json"}
    payload = {
        "lastname": "Brown",
        "totalprice": 111,
        "depositpaid": True,
        "bookingdates": {
            "checkin": "2024-01-01",
            "checkout": "2024-01-10"
        },
        "additionalneeds": "Breakfast"
    }

    response = requests.post(url, headers=headers, json=payload)
    # API does NOT validate strictly — returns 200 even with missing fields
    # So we treat this as 'permissive behavior' but still assert actual observed status
    assert response.status_code == 200
    assert "bookingid" in response.json()

import pytest
import requests

def test_get_booking_existing_id():
    # First create a booking to get a valid ID
    create_url = "https://restful-booker.herokuapp.com/booking"
    headers = {"Content-Type": "application/json"}
    payload = {
        "firstname": "Test",
        "lastname": "User",
        "totalprice": 100,
        "depositpaid": True,
        "bookingdates": {
            "checkin": "2024-01-01",
            "checkout": "2024-01-05"
        },
        "additionalneeds": "WiFi"
    }
    create_resp = requests.post(create_url, headers=headers, json=payload)
    assert create_resp.status_code == 200
    booking_id = create_resp.json()["bookingid"]

    # Then GET it
    get_url = f"https://restful-booker.herokuapp.com/booking/{booking_id}"
    get_headers = {"Accept": "application/json"}
    get_resp = requests.get(get_url, headers=get_headers)
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["firstname"] == "Test"
    assert data["lastname"] == "User"
    assert data["bookingdates"]["checkin"] == "2024-01-01"
    assert data["bookingdates"]["checkout"] == "2024-01-05"

import pytest
import requests

def test_get_booking_nonexistent_id():
    invalid_id = 999999999
    url = f"https://restful-booker.herokuapp.com/booking/{invalid_id}"
    headers = {"Accept": "application/json"}
    response = requests.get(url, headers=headers)
    assert response.status_code == 404

import pytest
import requests

def test_delete_booking_valid_id_authenticated():
    # Create booking first
    create_url = "https://restful-booker.herokuapp.com/booking"
    headers = {"Content-Type": "application/json"}
    payload = {
        "firstname": "DelTest",
        "lastname": "User",
        "totalprice": 200,
        "depositpaid": False,
        "bookingdates": {
            "checkin": "2024-02-01",
            "checkout": "2024-02-05"
        },
        "additionalneeds": "Late checkout"
    }
    create_resp = requests.post(create_url, headers=headers, json=payload)
    assert create_resp.status_code == 200
    booking_id = create_resp.json()["bookingid"]

    # Delete with auth
    delete_url = f"https://restful-booker.herokuapp.com/booking/{booking_id}"
    delete_headers = {
        "Content-Type": "application/json",
        "Authorization": "Basic YWRtaW46cGFzc3dvcmQxMjM="
    }
    delete_resp = requests.delete(delete_url, headers=delete_headers)
    assert delete_resp.status_code == 201  # Per spec: success returns 201

    # Verify deletion via GET → should 404
    get_url = f"https://restful-booker.herokuapp.com/booking/{booking_id}"
    get_headers = {"Accept": "application/json"}
    get_resp = requests.get(get_url, headers=get_headers)
    assert get_resp.status_code == 404

import pytest
import requests

def test_delete_booking_unauthenticated():
    # Create booking first
    create_url = "https://restful-booker.herokuapp.com/booking"
    headers = {"Content-Type": "application/json"}
    payload = {
        "firstname": "UnauthDel",
        "lastname": "Test",
        "totalprice": 150,
        "depositpaid": True,
        "bookingdates": {
            "checkin": "2024-03-01",
            "checkout": "2024-03-03"
        },
        "additionalneeds": "Parking"
    }
    create_resp = requests.post(create_url, headers=headers, json=payload)
    assert create_resp.status_code == 200
    booking_id = create_resp.json()["bookingid"]

    # Try delete without auth header
    delete_url = f"https://restful-booker.herokuapp.com/booking/{booking_id}"
    delete_headers = {"Content-Type": "application/json"}
    delete_resp = requests.delete(delete_url, headers=delete_headers)
    assert delete_resp.status_code == 401  # Unauthorized

import pytest
import requests

def test_delete_booking_nonexistent_id_authenticated():
    invalid_id = 999999999
    delete_url = f"https://restful-booker.herokuapp.com/booking/{invalid_id}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Basic YWRtaW46cGFzc3dvcmQxMjM="
    }
    response = requests.delete(delete_url, headers=headers)
    # Observed behavior: returns 405 Method Not Allowed for non-existent IDs
    # But per docs/spec not defined; actual prod returns 405 or 404 inconsistently
    # We assert safe: must NOT be 201
    assert response.status_code != 201
    assert response.status_code in [404, 405]