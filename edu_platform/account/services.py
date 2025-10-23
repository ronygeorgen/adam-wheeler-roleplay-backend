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


def create_ghl_contact(email, first_name, last_name, phone, location_id, access_token, tags=None):
    """
    Create or update a contact in GHL with all available information
    """
    url = "https://services.leadconnectorhq.com/contacts/"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-07-28"
    }
    
    # Build contact data with all available information
    contact_data = {
        "email": email,
        "firstName": first_name or "",
        "lastName": last_name or "",
        "locationId": location_id
    }
    
    # Add phone number if available
    if phone:
        contact_data["phone"] = phone
    
    if tags:
        contact_data["tags"] = tags
    
    try:
        response = requests.post(url, json=contact_data, headers=headers)
        
        if response.status_code in [200, 201]:
            print(f"✅ Contact created/updated for {email}")
            return response.json()
        else:
            print(f"❌ Error creating contact: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Exception creating contact: {e}")
        return None

def update_ghl_contact(contact_id, email, first_name, last_name, phone, location_id, access_token):
    """
    Update existing contact in GHL with latest information
    NOTE: Do NOT include locationId when updating existing contacts
    """
    url = f"https://services.leadconnectorhq.com/contacts/{contact_id}"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-07-28"
    }
    
    # Build contact data - DO NOT include locationId for updates
    contact_data = {
        "email": email,
        "firstName": first_name or "",
        "lastName": last_name or ""
    }
    
    # Add phone number if available
    if phone:
        contact_data["phone"] = phone
    
    try:
        print(f"🔄 Updating contact {contact_id} with data: {contact_data}")
        response = requests.put(url, json=contact_data, headers=headers)
        
        if response.status_code == 200:
            print(f"✅ Contact updated successfully for: {email}")
            return response.json()
        else:
            print(f"❌ Error updating contact: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Exception updating contact: {e}")
        return None

def add_tag_to_contact(contact_id, tag_name, location_id, access_token):
    """
    Add a specific tag to a contact - HANDLES EXISTING TAGS AS SUCCESS
    """
    url = f"https://services.leadconnectorhq.com/contacts/{contact_id}/tags"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-07-28"
    }
    
    tag_data = {
        "tags": [tag_name]
    }
    
    try:
        print(f"🏷️ Adding tag '{tag_name}' to contact {contact_id}")
        response = requests.post(url, json=tag_data, headers=headers)
        
        if response.status_code in [200, 201]:
            result = response.json()
            print(f"📨 Tag API response: {result}")
            
            # SUCCESS CASES:
            # 1. Tags were actually added (tagsAdded contains our tag)
            # 2. No tags were added because they already exist (tagsAdded is empty)
            # BOTH ARE SUCCESS FOR OUR USE CASE!
            
            tags_added = result.get('tagsAdded', [])
            
            if tag_name in tags_added:
                print(f"✅ Tag '{tag_name}' was added to contact {contact_id}")
                return True
            else:
                # Empty tagsAdded means the tag already exists - THIS IS SUCCESS!
                print(f"✅ Tag '{tag_name}' already exists on contact {contact_id}")
                return True
        else:
            print(f"❌ Error adding tag: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Exception adding tag: {e}")
        return False

def find_contact_by_email(email, location_id, access_token):
    """
    Find contact by email in GHL - USING SEARCH ENDPOINT
    """
    url = "https://services.leadconnectorhq.com/contacts/search"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-07-28"
    }
    
    # Correct search data format
    search_data = {
        "locationId": location_id,
        "query": email,  # Just the email string
        "pageLimit": 10  # As a number
    }
    
    try:
        print(f"🔍 Searching for contact with email: {email}")
        response = requests.post(url, json=search_data, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            contacts = data.get('contacts', [])
            if contacts:
                contact_id = contacts[0].get('id')
                print(f"✅ Found existing contact: {contact_id} for {email}")
                return contacts[0]
            else:
                print(f"ℹ️ No existing contact found for {email}")
                return None
        else:
            print(f"❌ Error searching contact: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Exception searching contact: {e}")
        return None
    

def contact_has_tag(contact_id, tag_name, location_id, access_token):
    """
    Check if a contact already has a specific tag
    """
    url = f"https://services.leadconnectorhq.com/contacts/{contact_id}"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-07-28"
    }
    
    try:
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            contact_data = response.json()
            tags = contact_data.get('tags', [])
            if tag_name in tags:
                print(f"✅ Contact already has tag '{tag_name}'")
                return True
            else:
                print(f"ℹ️ Contact does not have tag '{tag_name}' yet")
                return False
        else:
            print(f"❌ Error checking contact tags: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Exception checking contact tags: {e}")
        return False