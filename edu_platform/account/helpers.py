from .models import GHLUser, GHLAuthCredentials
from .services import get_ghl_users, get_ghl_user
from django.utils.timezone import now

def sync_ghl_users(location_id, access_token):
    """
    Sync all users from GHL for a location
    """
    try:
        location = GHLAuthCredentials.objects.get(location_id=location_id)
        
        # Get users from GHL
        users_data = get_ghl_users(location_id, access_token)
        
        if users_data and isinstance(users_data, dict) and 'users' in users_data:
            users_list = users_data['users']
            synced_count = 0
            
            for user_data in users_list:
                user_id = user_data.get('id')
                if not user_id:
                    continue
                
                # Create or update user
                user_obj, created = GHLUser.objects.update_or_create(
                    user_id=user_id,
                    location=location,
                    defaults={
                        'name': user_data.get('name', ''),
                        'first_name': user_data.get('firstName', ''),
                        'last_name': user_data.get('lastName', ''),
                        'email': user_data.get('email', ''),
                        'phone': user_data.get('phone', ''),
                        'role': user_data.get('role', ''),
                        'status': user_data.get('status', 'active'),
                    }
                )
                synced_count += 1
            
            print(f"Synced {synced_count} users for location {location_id}")
            return synced_count
        else:
            print(f"No users found or error in response for location {location_id}")
            return 0
            
    except Exception as e:
        print(f"Error syncing users for location {location_id}: {e}")
        return 0

def handle_user_webhook(data, event_type):
    """
    Handle user-related webhook events
    """
    try:
        credentials = GHLAuthCredentials.objects.first()
        if not credentials:
            print("No GHL credentials found for webhook")
            return

        access_token = credentials.access_token
        
        if event_type in ["UserCreated", "UserUpdated"]:
            user_id = data.get("userId") or data.get("id")
            if user_id:
                user_data = get_ghl_user(user_id, access_token)
                if user_data and 'user' in user_data:
                    user_info = user_data['user']
                    location = GHLAuthCredentials.objects.get(location_id=user_info.get('locationId'))
                    
                    GHLUser.objects.update_or_create(
                        user_id=user_id,
                        location=location,
                        defaults={
                            'name': user_info.get('name', ''),
                            'first_name': user_info.get('firstName', ''),
                            'last_name': user_info.get('lastName', ''),
                            'email': user_info.get('email', ''),
                            'phone': user_info.get('phone', ''),
                            'role': user_info.get('role', ''),
                            'status': user_info.get('status', 'active'),
                        }
                    )
                    print(f"User {user_id} processed via webhook: {event_type}")
                    
        elif event_type == "UserDeleted":
            user_id = data.get("userId") or data.get("id")
            if user_id:
                deleted_count = GHLUser.objects.filter(user_id=user_id).delete()[0]
                print(f"User {user_id} deleted via webhook: {deleted_count} records removed")
                
    except Exception as e:
        print(f"Error handling user webhook {event_type}: {e}")