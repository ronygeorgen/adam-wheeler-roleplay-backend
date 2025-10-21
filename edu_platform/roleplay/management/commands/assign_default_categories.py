# roleplay/management/commands/assign_default_categories.py
from django.core.management.base import BaseCommand
from account.models import GHLUser
from roleplay.models import Category, UserCategoryAssignment

class Command(BaseCommand):
    help = 'Assign default categories to all existing active users'

    def handle(self, *args, **options):
        default_categories = Category.objects.filter(is_default=True)
        active_users = GHLUser.objects.filter(status='active')
        
        assignments_created = 0
        users_processed = 0
        
        for user in active_users:
            users_processed += 1
            for category in default_categories:
                # Check if assignment already exists
                if not UserCategoryAssignment.objects.filter(user=user, category=category).exists():
                    UserCategoryAssignment.objects.create(user=user, category=category)
                    assignments_created += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Assigned category "{category.name}" to user "{user.name}"'
                        )
                    )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully assigned {assignments_created} default category assignments '
                f'to {users_processed} active users from {default_categories.count()} default categories'
            )
        )