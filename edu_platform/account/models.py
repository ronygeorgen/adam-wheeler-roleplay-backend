from django.db import models

class GHLAuthCredentials(models.Model):
    user_id = models.CharField(max_length=255)
    access_token = models.TextField()
    refresh_token = models.TextField()
    expires_in = models.IntegerField()
    scope = models.CharField(max_length=500, null=True, blank=True)
    user_type = models.CharField(max_length=50, null=True, blank=True)
    company_id = models.CharField(max_length=255, null=True, blank=True)
    location_id = models.CharField(max_length=255, unique=True)
    location_name = models.CharField(max_length=255, null=True, blank=True)
    timezone = models.CharField(max_length=100, null=True, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.location_name} - {self.location_id}"

class GHLUser(models.Model):
    user_id = models.CharField(max_length=255, unique=True)
    location = models.ForeignKey(GHLAuthCredentials, on_delete=models.CASCADE, related_name='users')
    name = models.CharField(max_length=255)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(max_length=255)
    phone = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=50, default="active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ghl_users'
    
    def __str__(self):
        return f"{self.name} - {self.email}"

class WebhookLog(models.Model):
    received_at = models.DateTimeField(auto_now_add=True)
    data = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"Webhook {self.id} : {self.received_at}"