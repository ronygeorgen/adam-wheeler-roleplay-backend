from django.db import models
from django.utils.timezone import now
import pytz

class Contact(models.Model):
    contact_id = models.CharField(max_length=255, unique=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    full_name_lowercase = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(max_length=255, blank=True, null=True)
    address = models.TextField(blank=True)
    country = models.CharField(max_length=10, blank=True)
    date_added = models.DateTimeField(default=now)
    date_updated = models.DateTimeField(auto_now=True)
    tags = models.JSONField(default=list, blank=True)
    source = models.CharField(max_length=100, default="ghl_api")
    
    class Meta:
        db_table = 'contacts'
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.contact_id})"

class Pipeline(models.Model):
    pipeline_id = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'pipelines'
    
    def __str__(self):
        return self.name

class PipelineStage(models.Model):
    pipeline_stage_id = models.CharField(max_length=255, unique=True)
    pipeline = models.ForeignKey(Pipeline, on_delete=models.CASCADE, related_name='stages')
    name = models.CharField(max_length=255)
    stage_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'pipeline_stages'
        ordering = ['stage_order']
    
    def __str__(self):
        return f"{self.pipeline.name} - {self.name}"

class Opportunity(models.Model):
    opportunity_id = models.CharField(max_length=255, unique=True)
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='opportunities')
    pipeline = models.ForeignKey(Pipeline, on_delete=models.SET_NULL, null=True, blank=True)
    current_stage = models.ForeignKey(PipelineStage, on_delete=models.SET_NULL, null=True, blank=True)
    created_by_source = models.CharField(max_length=50, default="ghl_api")
    created_by_channel = models.CharField(max_length=50, default="ghl_api")
    source_id = models.CharField(max_length=255, blank=True)
    created_timestamp = models.DateTimeField(default=now)
    value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    assigned = models.CharField(max_length=150, blank=True)
    tags = models.TextField(blank=True)
    engagement_score = models.IntegerField(default=0)
    status = models.CharField(max_length=50, null=True, blank=True)
    description = models.TextField(blank=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'opportunities'
        verbose_name_plural = 'opportunities'
    
    def __str__(self):
        return f"Opportunity {self.opportunity_id} - {self.contact.first_name} {self.contact.last_name}"