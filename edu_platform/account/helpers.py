from django.db import transaction
from .models import GHLUser, GHLAuthCredentials
from .services import get_ghl_users, get_ghl_user
from roleplay.models import Category, UserCategoryAssignment
from django.utils.timezone import now

def sync_ghl_users(location_id, access_token):
    """
    Sync all users from GHL for a location and auto-assign all categories to NEW users only
    """
    try:
        location = GHLAuthCredentials.objects.get(location_id=location_id)
        
        # Get users from GHL
        users_data = get_ghl_users(location_id, access_token)
        
        if users_data and isinstance(users_data, dict) and 'users' in users_data:
            users_list = users_data['users']
            synced_count = 0
            assignments_created = 0
            
            # Get all existing categories once
            all_categories = Category.objects.all()
            
            for user_data in users_list:
                user_id = user_data.get('id')
                if not user_id:
                    continue
                
                # Create or update user with ALL available data including phone
                user_obj, created = GHLUser.objects.update_or_create(
                    user_id=user_id,
                    location=location,
                    defaults={
                        'location_ghl_id': location_id,
                        'name': user_data.get('name', ''),
                        'first_name': user_data.get('firstName', ''),
                        'last_name': user_data.get('lastName', ''),
                        'email': user_data.get('email', ''),
                        'phone': user_data.get('phone', ''),
                        'role': user_data.get('role', ''),
                        'status': user_data.get('status', 'active'),
                    }
                )
                
                # AUTO-ASSIGN ALL CATEGORIES ONLY TO NEWLY CREATED USERS
                if created and all_categories.exists():
                    for category in all_categories:
                        assignment, assignment_created = UserCategoryAssignment.objects.get_or_create(
                            user=user_obj,
                            category=category
                        )
                        if assignment_created:
                            assignments_created += 1
                            print(f"✅ Auto-assigned category {category.name} to new user: {user_obj.email}")
                            # The signal will automatically trigger GHL notification
                
                synced_count += 1
            
            print(f"Synced {synced_count} users for location {location_id}")
            print(f"Created {assignments_created} category assignments for new users")
            return synced_count
            
        else:
            print(f"No users found or error in response for location {location_id}")
            return 0
            
    except Exception as e:
        print(f"Error syncing users for location {location_id}: {e}")
        return 0

def assign_all_categories_to_users(location_id):
    """
    Assign all existing categories to all users in a location
    """
    try:
        with transaction.atomic():
            # Get all users for the location - use the new location_ghl_id field
            users = GHLUser.objects.filter(location_ghl_id=location_id)  # CHANGE THIS LINE
            
            print(f"DEBUG: Looking for users with location_ghl_id: {location_id}")
            print(f"DEBUG: Found {users.count()} users")
            
            # Get all categories
            categories = Category.objects.all()
            print(f"DEBUG: Found {categories.count()} categories")
            
            assignments_created = 0
            
            for user in users:
                print(f"DEBUG: Processing user: {user.email} (ID: {user.user_id})")
                for category in categories:
                    # Create assignment if it doesn't exist
                    assignment, created = UserCategoryAssignment.objects.get_or_create(
                        user=user,
                        category=category
                    )
                    if created:
                        assignments_created += 1
                        print(f"DEBUG: Created assignment for user {user.email} to category {category.name}")
            
            print(f"DEBUG: Total assignments created: {assignments_created}")
            
            return {
                'success': True,
                'users_count': users.count(),
                'categories_count': categories.count(),
                'assignments_created': assignments_created
            }
            
    except Exception as e:
        print(f"DEBUG: Error in assign_all_categories_to_users: {e}")
        return {
            'success': False,
            'error': str(e)
        }
    
def handle_user_webhook(data, event_type):
    """
    Handle user webhook events and automatically assign categories to new users
    Also update GHL contacts when user information changes
    """
    try:
        location_id = data.get("locationId")
        user_id = data.get("id")
        first_name = data.get("firstName")
        last_name = data.get("lastName")
        email = data.get("email")
        phone = data.get("phone")  # Get phone from webhook
        
        print(f"🔄 Processing webhook: {event_type} for user: {email}")
        
        if not location_id or not user_id:
            print(f"❌ Invalid webhook data: location_id={location_id}, user_id={user_id}")
            return

        # Map GHL event types to your expected types
        event_type_map = {
            "UserCreate": "UserCreated",
            "UserUpdate": "UserUpdated", 
            "UserDelete": "UserDeleted"
        }
        
        mapped_event_type = event_type_map.get(event_type, event_type)
        print(f"📋 Event type mapped: {event_type} -> {mapped_event_type}")

        if mapped_event_type in ["UserCreated", "UserUpdated"]:
            try:
                location = GHLAuthCredentials.objects.get(location_id=location_id)
            except GHLAuthCredentials.DoesNotExist:
                print(f"❌ Location not found: {location_id}")
                return

            # Create or update user - data is at root level, not nested
            user, created = GHLUser.objects.update_or_create(
                user_id=user_id,
                defaults={
                    'location': location,
                    'location_ghl_id': location_id,
                    'name': f"{first_name or ''} {last_name or ''}".strip(),
                    'first_name': first_name or '',
                    'last_name': last_name or '',
                    'email': email or '',
                    'phone': phone or '',  # Update phone field
                    'role': data.get('role', ''),
                    'status': 'active'
                }
            )
            
            print(f"👤 User {'created' if created else 'updated'}: {user.email}")
            
            # If this is a new user, assign all categories to them
            if created:
                categories = Category.objects.all()
                if categories.exists():
                    assignments_created = 0
                    for category in categories:
                        assignment, assignment_created = UserCategoryAssignment.objects.get_or_create(
                            user=user,
                            category=category
                        )
                        if assignment_created:
                            assignments_created += 1
                    
                    print(f"✅ Auto-assigned {assignments_created} categories to new user: {user.email}")
                else:
                    print(f"⚠️ No categories available to assign to new user: {user.email}")
            
            # For UserUpdated events, also ensure the contact info is updated in GHL
            if mapped_event_type == "UserUpdated":
                from account.tasks import update_user_contact_task
                update_user_contact_task.delay(
                    user_email=user.email,
                    user_first_name=user.first_name,
                    user_last_name=user.last_name,
                    user_phone=user.phone,
                    location_id=user.location_ghl_id,
                    access_token=location.access_token
                )
                print(f"📞 Contact update queued for: {user.email}")
                
        elif mapped_event_type == "UserDeleted":
            # Delete user and their category assignments
            try:
                user = GHLUser.objects.get(user_id=user_id)
                # Delete category assignments first (due to foreign key constraints)
                UserCategoryAssignment.objects.filter(user=user).delete()
                # Then delete the user
                user.delete()
                print(f"🗑️ Deleted user and their category assignments: {user_id}")
            except GHLUser.DoesNotExist:
                print(f"⚠️ User not found for deletion: {user_id}")
            
        print(f"✅ Webhook {mapped_event_type} processed successfully for user: {email}")
            
    except Exception as e:
        print(f"❌ Error handling user webhook: {e}")
        import traceback
        traceback.print_exc()