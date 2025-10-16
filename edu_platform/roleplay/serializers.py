from rest_framework import serializers
from .models import Category, Model, UserCategoryAssignment, Feedback, RoleplayScore
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


class FeedbackSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    location_id = serializers.CharField(source='user.location_ghl_id', read_only=True)
    
    class Meta:
        model = Feedback
        fields = [
            'id', 'user', 'user_name', 'user_email', 'location_id',
            'first_name', 'last_name', 'email', 'score', 'strengths', 
            'improvements', 'submitted_at'
        ]
        read_only_fields = ['user', 'submitted_at']
    
    def validate_email(self, value):
        """
        Validate that the email matches an active GHL user
        """
        try:
            user = GHLUser.objects.get(email=value, status='active')
        except GHLUser.DoesNotExist:
            raise serializers.ValidationError(
                "No active user found with this email. Please use the email you used for training onboarding."
            )
        return value
    
    def validate_score(self, value):
        """
        Validate score is between reasonable limits
        """
        if value < 0 or value > 100:
            raise serializers.ValidationError("Score must be between 0 and 100")
        return value
    
    def create(self, validated_data):
        """
        Automatically associate feedback with GHL user based on email
        """
        email = validated_data.get('email')
        try:
            user = GHLUser.objects.get(email=email, status='active')
            validated_data['user'] = user
            return super().create(validated_data)
        except GHLUser.DoesNotExist:
            raise serializers.ValidationError({
                "email": "No active user found with this email."
            })

class RoleplayScoreSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    model_name = serializers.CharField(source='model.name', read_only=True)
    category_name = serializers.CharField(source='model.category.name', read_only=True)
    
    class Meta:
        model = RoleplayScore
        fields = [
            'id', 'user', 'user_name', 'user_email', 'model', 'model_name',
            'category_name', 'score', 'raw_score', 'submitted_at'
        ]
        read_only_fields = ['submitted_at']
    
    def create(self, validated_data):
        # Ensure one score per user per model (update if exists)
        user = validated_data.get('user')
        model = validated_data.get('model')
        
        instance, created = RoleplayScore.objects.update_or_create(
            user=user,
            model=model,
            defaults=validated_data
        )
        return instance

class ScoreSubmissionSerializer(serializers.Serializer):
    """Serializer for direct score submission from frontend"""
    email = serializers.EmailField()
    model_id = serializers.IntegerField()
    score = serializers.IntegerField(min_value=0, max_value=100)
    raw_score = serializers.CharField(required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    
    def validate_email(self, value):
        try:
            user = GHLUser.objects.get(email=value, status='active')
            return value
        except GHLUser.DoesNotExist:
            raise serializers.ValidationError("No active user found with this email")
    
    def validate_model_id(self, value):
        try:
            model = Model.objects.get(id=value)
            return value
        except Model.DoesNotExist:
            raise serializers.ValidationError("Model not found")
    user_name = serializers.CharField(source='user.name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    
    class Meta:
        model = Feedback
        fields = [
            'id', 'user', 'user_name', 'user_email', 'first_name', 'last_name', 
            'email', 'score', 'strengths', 'improvements', 'submitted_at'
        ]
        read_only_fields = ['user', 'submitted_at']
    
    def validate_email(self, value):
        """
        Validate that the email matches the authenticated user's email
        """
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            # If you have user authentication, you can add validation here
            pass
        return value
    
    def validate_score(self, value):
        """
        Validate score is between reasonable limits
        """
        if value < 0 or value > 100:
            raise serializers.ValidationError("Score must be between 0 and 100")
        return value