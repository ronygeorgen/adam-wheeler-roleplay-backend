from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from account.models import GHLUser
from .models import Category, UserCategoryAssignment

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