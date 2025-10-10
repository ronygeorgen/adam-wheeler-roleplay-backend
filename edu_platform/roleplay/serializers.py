from rest_framework import serializers
from .models import Category, Model, UserCategoryAssignment
from account.models import GHLUser

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'created_at', 'updated_at']

class ModelSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = Model
        fields = '__all__'

class GHLUserSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source='location.location_name', read_only=True)
    location_id = serializers.CharField(source='location_ghl_id', read_only=True)  # CHANGE THIS LINE
    assigned_categories = serializers.SerializerMethodField()
    
    class Meta:
        model = GHLUser
        fields = [
            'user_id', 'name', 'first_name', 'last_name', 'email', 
            'phone', 'role', 'status', 'location', 'location_name', 'location_id',
            'assigned_categories', 'created_at', 'updated_at'
        ]

    def get_assigned_categories(self, obj):
        assignments = UserCategoryAssignment.objects.filter(user=obj).select_related('category')
        return CategorySerializer([ass.category for ass in assignments], many=True).data