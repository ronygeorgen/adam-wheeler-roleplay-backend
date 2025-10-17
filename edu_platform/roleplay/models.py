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
    

class Feedback(models.Model):
    user = models.ForeignKey(GHLUser, on_delete=models.CASCADE, related_name='feedbacks')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    # Link feedback to the specific roleplay model attempted; category is derivable via model.category
    model = models.ForeignKey('Model', on_delete=models.SET_NULL, null=True, blank=True, related_name='feedbacks')
    score = models.IntegerField()
    strengths = models.TextField(help_text="What did you do well?")
    improvements = models.TextField(help_text="What could you improve?")
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'feedback_submissions'
        ordering = ['-submitted_at']
    
    def __str__(self):
        return f"Feedback from {self.first_name} {self.last_name} - Score: {self.score}"
    

class RoleplayScore(models.Model):
    """Model to store roleplay scores separately if needed"""
    user = models.ForeignKey(GHLUser, on_delete=models.CASCADE, related_name='scores')
    model = models.ForeignKey(Model, on_delete=models.CASCADE, related_name='scores')
    score = models.IntegerField()
    raw_score = models.CharField(max_length=50, blank=True, null=True)  # Store the original score string like "85%"
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'roleplay_scores'
        ordering = ['-submitted_at']
        unique_together = ['user', 'model']  # One score per user per model
    
    def __str__(self):
        return f"{self.user.name} - {self.model.name}: {self.score}%"