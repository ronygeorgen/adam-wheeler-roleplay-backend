from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from account.models import GHLUser
from .models import Category, UserCategoryAssignment
from account.models import GHLAuthCredentials
from account.tasks import notify_category_assignment_task

@receiver(post_save, sender=GHLUser)
def assign_default_categories_to_user(sender, instance, created, **kwargs):
    """
    Assign ALL default categories when:
    1. New user is created AND active
    2. Existing user becomes active (status changed to active)
    """
    if instance.status == 'active':
        default_categories = Category.objects.filter(is_default=True)
        for category in default_categories:
            UserCategoryAssignment.objects.get_or_create(
                user=instance, 
                category=category
            )

@receiver(pre_save, sender=GHLUser)
def handle_user_activation(sender, instance, **kwargs):
    """
    Handle when existing users become active
    """
    if instance.pk:  # Existing user
        try:
            old_instance = GHLUser.objects.get(pk=instance.pk)
            # If user was not active but now becoming active
            if old_instance.status != 'active' and instance.status == 'active':
                # The post_save signal will handle the assignment
                pass
        except GHLUser.DoesNotExist:
            pass

@receiver(post_save, sender=UserCategoryAssignment)
def handle_category_assignment(sender, instance, created, **kwargs):
    """
    Signal handler for when a category is assigned to a user
    Creates/updates contact in GHL with all user info and adds/updates "category added" tag
    """
    user = instance.user
    category = instance.category
    
    # Only proceed if user is active
    if user.status != 'active':
        print(f"⚠️ User {user.email} is not active, skipping GHL notification")
        return
        
    # Get location credentials
    try:
        location_credentials = GHLAuthCredentials.objects.get(location_id=user.location_ghl_id)
        
        # Trigger async task to handle GHL operations with all user data
        # NOTE: We're triggering this for BOTH new AND existing assignments
        notify_category_assignment_task.delay(
            user_email=user.email,
            user_first_name=user.first_name,
            user_last_name=user.last_name,
            user_phone=user.phone,
            location_id=user.location_ghl_id,
            access_token=location_credentials.access_token,
            category_name=category.name,
            is_new_assignment=created  # Pass whether this is a new assignment
        )
        
        print(f"✅ Category assignment {'created' if created else 'updated'} notification queued for {user.email}")
        
    except GHLAuthCredentials.DoesNotExist:
        print(f"❌ Location credentials not found for {user.location_ghl_id}")
    except Exception as e:
        print(f"❌ Error in category assignment signal: {e}")

@receiver(post_save, sender=Category)
def handle_default_category_change(sender, instance, **kwargs):
    """
    When a category is marked as default, assign it to all active users
    and trigger GHL notifications
    """
    # Check if is_default is being changed to True
    is_new_default = False
    if instance.pk:  # Existing instance
        try:
            old_instance = Category.objects.get(pk=instance.pk)
            if not old_instance.is_default and instance.is_default:
                is_new_default = True
        except Category.DoesNotExist:
            pass
    else:  # New instance
        if instance.is_default:
            is_new_default = True
    
    # If this category is now default, assign it to all active users
    if is_new_default:
        active_users = GHLUser.objects.filter(status='active')
        
        for user in active_users:
            assignment, created = UserCategoryAssignment.objects.get_or_create(
                user=user,
                category=instance
            )
            
            if created:
                print(f"✅ Auto-assigned new default category '{instance.name}' to user: {user.email}")
                # This will trigger the handle_category_assignment signal above