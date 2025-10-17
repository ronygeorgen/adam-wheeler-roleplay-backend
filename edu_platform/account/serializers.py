from rest_framework import serializers
from .models import GHLUser, GHLAuthCredentials
from roleplay.models import UserCategoryAssignment
from roleplay.serializers import CategorySerializer

class GHLAuthCredentialsSerializer(serializers.ModelSerializer):
    class Meta:
        model = GHLAuthCredentials
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
        assignments = UserCategoryAssignment.objects.filter(user=obj)
        categories = [assignment.category for assignment in assignments]
        return CategorySerializer(categories, many=True).data

class LocationWithUsersSerializer(serializers.ModelSerializer):
    users = GHLUserSerializer(many=True, read_only=True)

    class Meta:
        model = GHLAuthCredentials
        fields = [
            'location_id', 'location_name', 'company_id', 'timezone',
            'user_id', 'scope', 'user_type', 'created_at', 'updated_at', 'users'
        ]