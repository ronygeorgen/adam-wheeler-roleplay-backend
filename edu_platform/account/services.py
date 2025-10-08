import requests
from django.conf import settings

def get_location_name(location_id, access_token):
    url = f"https://services.leadconnectorhq.com/locations/{location_id}"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-07-28"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        location_data = data.get("location", {})
        return location_data.get("name"), location_data.get("timezone")
    
    except requests.exceptions.RequestException as e:
        print(f"Error fetching location: {e}")
        return None, "UTC"

def get_ghl_users(location_id, access_token):
    """Get all users for a location"""
    url = "https://services.leadconnectorhq.com/users/"  # Correct endpoint
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-07-28"
    }
    
    # Add locationId as query parameter
    params = {
        "locationId": location_id
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error fetching users: {response.status_code} - {response.text}")
            return {"error": response.status_code, "message": response.text}
    except Exception as e:
        print(f"Exception fetching users: {e}")
        return {"error": "exception", "message": str(e)}

def get_ghl_user(user_id, access_token):
    """Get specific user details"""
    url = f"https://services.leadconnectorhq.com/users/{user_id}"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-07-28"
    }
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": response.status_code, "message": response.text}
    except Exception as e:
        return {"error": "exception", "message": str(e)}