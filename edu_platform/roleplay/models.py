from django.db import models
from account.models import GHLUser

class Category(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Model(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='models')
    name = models.CharField(max_length=255)
    iframe_code = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.category.name}"

class UserCategoryAssignment(models.Model):
    user = models.ForeignKey(GHLUser, on_delete=models.CASCADE, related_name='assigned_categories')
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'category']

    def __str__(self):
        return f"{self.user.name} - {self.category.name}"