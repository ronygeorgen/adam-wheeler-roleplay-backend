from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework import serializers
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Avg, Count, Q, Max, Min
from .models import Category, Model, UserCategoryAssignment, Feedback, RoleplayScore
from account.models import GHLUser
from .serializers import (
    CategorySerializer, ModelSerializer, 
    GHLUserSerializer, FeedbackSerializer,
    RoleplayScoreSerializer, ScoreSubmissionSerializer
)

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

class ModelViewSet(viewsets.ModelViewSet):
    queryset = Model.objects.all()
    serializer_class = ModelSerializer

    def get_queryset(self):
        queryset = Model.objects.all()
        category_id = self.request.query_params.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        return queryset

class GHLUserViewSet(viewsets.ViewSet):
    def list(self, request):
        location_id = request.query_params.get('location')
        users = GHLUser.objects.all()
        
        if location_id:
            users = users.filter(location__location_id=location_id)
        
        serializer = GHLUserSerializer(users, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        user = get_object_or_404(GHLUser, user_id=pk)
        serializer = GHLUserSerializer(user)
        return Response(serializer.data)

    def partial_update(self, request, pk=None):
        user = get_object_or_404(GHLUser, user_id=pk)
        serializer = GHLUserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def assign_categories(self, request, pk=None):
        user = get_object_or_404(GHLUser, user_id=pk)
        category_ids = request.data.get('category_ids', [])
        
        # Clear existing assignments
        UserCategoryAssignment.objects.filter(user=user).delete()
        
        # Create new assignments
        for category_id in category_ids:
            try:
                category = Category.objects.get(id=category_id)
                UserCategoryAssignment.objects.create(user=user, category=category)
            except Category.DoesNotExist:
                return Response(
                    {"error": f"Category with id {category_id} does not exist"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Return updated user data
        serializer = GHLUserSerializer(user)
        return Response(serializer.data)
    
    def destroy(self, request, pk=None):
        user = get_object_or_404(GHLUser, user_id=pk)
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class UserAccessViewSet(viewsets.ViewSet):
    @action(detail=False, methods=['get'])
    def get_user_categories(self, request):
        email = request.query_params.get('email')
        if not email:
            return Response(
                {"error": "Email parameter is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = GHLUser.objects.get(email=email, status='active')
            assigned_categories = UserCategoryAssignment.objects.filter(user=user)
            
            categories_data = []
            for assignment in assigned_categories:
                category = assignment.category
                models = Model.objects.filter(category=category)
                
                categories_data.append({
                    'id': category.id,
                    'name': category.name,
                    'models': ModelSerializer(models, many=True).data
                })
            
            return Response({
                'user': {
                    'name': user.name,
                    'email': user.email,
                    'location_id': user.location_ghl_id  # CHANGE THIS LINE
                },
                'categories': categories_data
            })
            
        except GHLUser.DoesNotExist:
            return Response(
                {"error": "User not found or inactive"}, 
                status=status.HTTP_404_NOT_FOUND
            )

class FeedbackViewSet(viewsets.ModelViewSet):
    queryset = Feedback.objects.all()
    serializer_class = FeedbackSerializer
    
    def get_queryset(self):
        """
        Return feedbacks based on query parameters
        """
        queryset = Feedback.objects.all()
        
        # Filter by location
        location_id = self.request.query_params.get('location_id')
        if location_id:
            queryset = queryset.filter(user__location_ghl_id=location_id)
        
        # Filter by user email
        user_email = self.request.query_params.get('user_email')
        if user_email:
            queryset = queryset.filter(email=user_email)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(submitted_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(submitted_at__date__lte=end_date)
            
        return queryset.select_related('user')
    
    @action(detail=False, methods=['get'])
    def user_feedback(self, request):
        """
        Get feedback for a specific user by email
        """
        email = request.query_params.get('email')
        if not email:
            return Response(
                {"error": "Email parameter is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        feedbacks = Feedback.objects.filter(email=email).select_related('user').order_by('-submitted_at')
        serializer = self.get_serializer(feedbacks, many=True)
        
        return Response({
            'email': email,
            'feedbacks_count': feedbacks.count(),
            'feedbacks': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def location_feedback(self, request):
        """
        Get all feedback for a specific location
        """
        location_id = request.query_params.get('location_id')
        if not location_id:
            return Response(
                {"error": "location_id parameter is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        feedbacks = Feedback.objects.filter(
            user__location_ghl_id=location_id
        ).select_related('user').order_by('-submitted_at')
        
        serializer = self.get_serializer(feedbacks, many=True)
        
        # Calculate average score for the location
        avg_score = feedbacks.aggregate(avg_score=Avg('score'))['avg_score'] or 0
        
        return Response({
            'location_id': location_id,
            'feedbacks_count': feedbacks.count(),
            'average_score': round(avg_score, 2),
            'feedbacks': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get feedback statistics
        """
        location_id = request.query_params.get('location_id')
        
        queryset = Feedback.objects.all()
        if location_id:
            queryset = queryset.filter(user__location_ghl_id=location_id)
        
        stats = queryset.aggregate(
            total_feedbacks=Count('id'),
            average_score=Avg('score'),
            min_score=Count('score', filter=Q(score__lt=70)),
            max_score=Count('score', filter=Q(score__gte=90))
        )
        
        return Response(stats)

class RoleplayScoreViewSet(viewsets.ModelViewSet):
    queryset = RoleplayScore.objects.all()
    serializer_class = RoleplayScoreSerializer
    
    def get_queryset(self):
        queryset = RoleplayScore.objects.all()
        
        # Filter by location
        location_id = self.request.query_params.get('location_id')
        if location_id:
            queryset = queryset.filter(user__location_ghl_id=location_id)
        
        # Filter by user email
        user_email = self.request.query_params.get('user_email')
        if user_email:
            queryset = queryset.filter(user__email=user_email)
        
        # Filter by model
        model_id = self.request.query_params.get('model_id')
        if model_id:
            queryset = queryset.filter(model_id=model_id)
            
        return queryset.select_related('user', 'model', 'model__category')
    
    @action(detail=False, methods=['post'])
    def submit_score(self, request):
        """
        Submit a roleplay score from frontend
        """
        serializer = ScoreSubmissionSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            model_id = serializer.validated_data['model_id']
            score = serializer.validated_data['score']
            raw_score = serializer.validated_data.get('raw_score', '')
            
            try:
                user = GHLUser.objects.get(email=email, status='active')
                model = Model.objects.get(id=model_id)
                
                # Create or update score
                roleplay_score, created = RoleplayScore.objects.update_or_create(
                    user=user,
                    model=model,
                    defaults={
                        'score': score,
                        'raw_score': raw_score
                    }
                )
                
                # Also create a feedback entry
                feedback = Feedback.objects.create(
                    user=user,
                    first_name=serializer.validated_data.get('first_name', user.first_name),
                    last_name=serializer.validated_data.get('last_name', user.last_name),
                    email=email,
                    score=score,
                    strengths="Auto-recorded from roleplay completion",
                    improvements="Auto-recorded from roleplay completion"
                )
                
                return Response({
                    'message': 'Score submitted successfully',
                    'score_id': roleplay_score.id,
                    'feedback_id': feedback.id,
                    'created': created
                }, status=status.HTTP_201_CREATED)
                
            except GHLUser.DoesNotExist:
                return Response(
                    {"error": "User not found"}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            except Model.DoesNotExist:
                return Response(
                    {"error": "Model not found"}, 
                    status=status.HTTP_404_NOT_FOUND
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def user_scores(self, request):
        """
        Get all scores for a specific user
        """
        email = request.query_params.get('email')
        if not email:
            return Response(
                {"error": "Email parameter is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        scores = RoleplayScore.objects.filter(
            user__email=email
        ).select_related('user', 'model', 'model__category').order_by('-submitted_at')
        
        serializer = self.get_serializer(scores, many=True)
        
        # Calculate user statistics
        user_stats = scores.aggregate(
            total_scores=Count('id'),
            average_score=Avg('score'),
            highest_score=Count('score', filter=Q(score__gte=90)),
            lowest_score=Count('score', filter=Q(score__lt=70))
        )
        
        return Response({
            'email': email,
            'stats': user_stats,
            'scores': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def leaderboard(self, request):
        """
        Get leaderboard for a location
        """
        location_id = request.query_params.get('location_id')
        if not location_id:
            return Response(
                {"error": "location_id parameter is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get top users by average score
        leaderboard = RoleplayScore.objects.filter(
            user__location_ghl_id=location_id
        ).values(
            'user__user_id', 'user__name', 'user__email'
        ).annotate(
            average_score=Avg('score'),
            tests_completed=Count('id')
        ).order_by('-average_score')[:10]  # Top 10
        
        return Response({
            'location_id': location_id,
            'leaderboard': list(leaderboard)
        })
    
class UserPerformanceViewSet(viewsets.ViewSet):
    """API for user performance dashboard"""
    
    @action(detail=False, methods=['get'])
    def user_stats(self, request):
        """
        Get user performance statistics by email
        """
        email = request.query_params.get('email')
        if not email:
            return Response(
                {"error": "Email parameter is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = GHLUser.objects.get(email=email, status='active')
            
            # Get all feedback and scores for this user
            feedbacks = Feedback.objects.filter(user=user).select_related('user')
            scores = RoleplayScore.objects.filter(user=user).select_related('model', 'model__category')
            
            # Overall statistics
            overall_stats = {
                'total_feedbacks': feedbacks.count(),
                'total_scores': scores.count(),
                'average_score': scores.aggregate(Avg('score'))['score__avg'] or 0,
                'highest_score': scores.aggregate(Max('score'))['score__max'] or 0,
                'lowest_score': scores.aggregate(Min('score'))['score__min'] or 0,
            }
            
            # Statistics by category
            category_stats = []
            categories = Category.objects.filter(
                models__scores__user=user
            ).distinct()
            
            for category in categories:
                category_scores = scores.filter(model__category=category)
                category_feedbacks = feedbacks.filter(
                    user=user,
                    score__in=category_scores.values_list('score', flat=True)
                )
                
                if category_scores.exists():
                    category_stats.append({
                        'category_id': category.id,
                        'category_name': category.name,
                        'attempts_count': category_scores.count(),
                        'average_score': category_scores.aggregate(Avg('score'))['score__avg'] or 0,
                        'highest_score': category_scores.aggregate(Max('score'))['score__max'] or 0,
                        'last_attempt': category_scores.latest('submitted_at').submitted_at if category_scores.exists() else None,
                        'feedbacks_count': category_feedbacks.count(),
                    })
            
            # Recent activity (last 10 activities)
            recent_activities = []
            recent_scores = scores.order_by('-submitted_at')[:10]
            recent_feedbacks = feedbacks.order_by('-submitted_at')[:10]
            
            # Combine and sort recent activities
            for score in recent_scores:
                recent_activities.append({
                    'type': 'score',
                    'model_name': score.model.name,
                    'category_name': score.model.category.name,
                    'score': score.score,
                    'timestamp': score.submitted_at,
                    'raw_score': score.raw_score,
                })
            
            for feedback in recent_feedbacks:
                recent_activities.append({
                    'type': 'feedback',
                    'score': feedback.score,
                    'timestamp': feedback.submitted_at,
                    'has_feedback': bool(feedback.strengths or feedback.improvements),
                })
            
            # Sort by timestamp and take latest 10
            recent_activities.sort(key=lambda x: x['timestamp'], reverse=True)
            recent_activities = recent_activities[:10]
            
            return Response({
                'user': {
                    'name': user.name,
                    'email': user.email,
                    'location_id': user.location_ghl_id,
                },
                'overall_stats': overall_stats,
                'category_stats': category_stats,
                'recent_activities': recent_activities,
            })
            
        except GHLUser.DoesNotExist:
            return Response(
                {"error": "User not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['get'])
    def category_performance(self, request):
        """
        Get detailed performance for a specific category
        """
        email = request.query_params.get('email')
        category_id = request.query_params.get('category_id')
        
        if not email or not category_id:
            return Response(
                {"error": "Email and category_id parameters are required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = GHLUser.objects.get(email=email, status='active')
            category = Category.objects.get(id=category_id)
            
            # Get scores for this category
            scores = RoleplayScore.objects.filter(
                user=user,
                model__category=category
            ).select_related('model').order_by('-submitted_at')
            
            # Get feedbacks for this category
            feedbacks = Feedback.objects.filter(
                user=user,
                score__in=scores.values_list('score', flat=True)
            ).order_by('-submitted_at')
            
            # Model-wise performance
            model_performance = []
            models = Model.objects.filter(category=category)
            
            for model in models:
                model_scores = scores.filter(model=model)
                if model_scores.exists():
                    model_performance.append({
                        'model_id': model.id,
                        'model_name': model.name,
                        'attempts_count': model_scores.count(),
                        'latest_score': model_scores.first().score,
                        'average_score': model_scores.aggregate(Avg('score'))['score__avg'] or 0,
                        'highest_score': model_scores.aggregate(Max('score'))['score__max'] or 0,
                        'last_attempt': model_scores.first().submitted_at,
                    })
            
            return Response({
                'category': {
                    'id': category.id,
                    'name': category.name,
                },
                'summary': {
                    'total_attempts': scores.count(),
                    'average_score': scores.aggregate(Avg('score'))['score__avg'] or 0,
                    'highest_score': scores.aggregate(Max('score'))['score__max'] or 0,
                    'feedbacks_count': feedbacks.count(),
                },
                'model_performance': model_performance,
                'recent_scores': RoleplayScoreSerializer(scores[:5], many=True).data,
                'recent_feedbacks': FeedbackSerializer(feedbacks[:5], many=True).data,
            })
            
        except GHLUser.DoesNotExist:
            return Response(
                {"error": "User not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Category.DoesNotExist:
            return Response(
                {"error": "Category not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )