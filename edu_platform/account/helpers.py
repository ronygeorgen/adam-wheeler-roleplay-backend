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
                
                # Create or update user
                user_obj, created = GHLUser.objects.update_or_create(
                    user_id=user_id,
                    location=location,
                    defaults={
                        'location_ghl_id': location_id,  # ADD THIS LINE - store the actual GHL location ID
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
                if created:
                    for category in all_categories:
                        assignment, assignment_created = UserCategoryAssignment.objects.get_or_create(
                            user=user_obj,
                            category=category
                        )
                        if assignment_created:
                            assignments_created += 1
                    print(f"Auto-assigned {all_categories.count()} categories to new user: {user_obj.email}")
                
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
    """
    try:
        location_id = data.get("locationId")
        user_data = data.get("user", {})
        
        if not location_id or not user_data:
            print(f"Invalid webhook data: location_id={location_id}, user_data={user_data}")
            return
        
        user_id = user_data.get("id")
        if not user_id:
            print("No user ID found in webhook data")
            return

        if event_type == "UserCreated":
            try:
                location = GHLAuthCredentials.objects.get(location_id=location_id)
            except GHLAuthCredentials.DoesNotExist:
                print(f"Location not found: {location_id}")
                return

            # Create or update user
            user, created = GHLUser.objects.update_or_create(
                user_id=user_id,
                defaults={
                    'location': location,
                    'location_ghl_id': location_id,  # ADD THIS LINE
                    'name': f"{user_data.get('firstName', '')} {user_data.get('lastName', '')}".strip(),
                    'first_name': user_data.get('firstName', ''),
                    'last_name': user_data.get('lastName', ''),
                    'email': user_data.get('email', ''),
                    'phone': user_data.get('phone', ''),
                    'role': user_data.get('role', ''),
                    'status': user_data.get('status', 'active')
                }
            )
            
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
                    
                    print(f"Auto-assigned {assignments_created} categories to new user: {user.email}")
                else:
                    print(f"No categories available to assign to new user: {user.email}")
                
        elif event_type == "UserUpdated":
            try:
                location = GHLAuthCredentials.objects.get(location_id=location_id)
                
                # Use update_or_create to handle both update and potential creation
                user, created = GHLUser.objects.update_or_create(
                    user_id=user_id,
                    defaults={
                        'location': location,
                        'name': f"{user_data.get('firstName', '')} {user_data.get('lastName', '')}".strip(),
                        'first_name': user_data.get('firstName', ''),
                        'last_name': user_data.get('lastName', ''),
                        'email': user_data.get('email', ''),
                        'phone': user_data.get('phone', ''),
                        'role': user_data.get('role', ''),
                        'status': user_data.get('status', 'active')
                    }
                )
                
                # If this was actually a creation (not just update), assign categories
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
                        
                        print(f"Auto-assigned {assignments_created} categories to new user (from update): {user.email}")
                
                print(f"Updated user: {user.email}")
                
            except GHLAuthCredentials.DoesNotExist:
                print(f"Location not found for user update: {location_id}")
            
        elif event_type == "UserDeleted":
            # Delete user and their category assignments
            try:
                user = GHLUser.objects.get(user_id=user_id)
                # Delete category assignments first (due to foreign key constraints)
                UserCategoryAssignment.objects.filter(user=user).delete()
                # Then delete the user
                user.delete()
                print(f"Deleted user and their category assignments: {user_id}")
            except GHLUser.DoesNotExist:
                print(f"User not found for deletion: {user_id}")
            
    except Exception as e:
        print(f"Error handling user webhook: {e}")
        import traceback
        traceback.print_exc()  # This will give you the full stack trace