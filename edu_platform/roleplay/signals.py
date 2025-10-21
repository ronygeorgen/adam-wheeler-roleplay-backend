from django.db.models.signals import post_save
from django.dispatch import receiver
from account.models import GHLUser
from .models import Category, UserCategoryAssignment

@receiver(post_save, sender=GHLUser)
def assign_default_categories_to_new_user(sender, instance, created, **kwargs):
    if created and instance.status == 'active':
        default_categories = Category.objects.filter(is_default=True)
        for category in default_categories:
            UserCategoryAssignment.objects.create(user=instance, category=category)