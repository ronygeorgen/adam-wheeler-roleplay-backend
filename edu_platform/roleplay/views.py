from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework import serializers
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Avg, Count, Q, Max, Min
from datetime import datetime, timezone
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
                
                # Create a feedback entry (now the source of truth for scores)
                feedback = Feedback.objects.create(
                    user=user,
                    first_name=serializer.validated_data.get('first_name', user.first_name),
                    last_name=serializer.validated_data.get('last_name', user.last_name),
                    email=email,
                    model=model,
                    score=score,
                    strengths="Auto-recorded from roleplay completion",
                    improvements="Auto-recorded from roleplay completion"
                )
                
                return Response({
                    'message': 'Score submitted successfully',
                    'feedback_id': feedback.id,
                    'created': True
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
        Get user performance for each category and each roleplay (model).
        Includes latest score and highest score per roleplay, category summaries,
        and the most recent roleplay the user tried with its category.
        """
        email = request.query_params.get('email')
        if not email:
            return Response(
                {"error": "Email parameter is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = GHLUser.objects.get(email=email, status='active')

            # All feedback entries for this user (with model info for roleplay linkage)
            feedbacks_qs = Feedback.objects.filter(user=user).select_related('model', 'model__category')

            # Overall stats
            overall_stats = {
                'total_feedbacks': feedbacks_qs.count(),
                'total_scores': feedbacks_qs.count(),
                'average_score': feedbacks_qs.aggregate(Avg('score'))['score__avg'] or 0,
                'highest_score': feedbacks_qs.aggregate(Max('score'))['score__max'] or 0,
                'lowest_score': feedbacks_qs.aggregate(Min('score'))['score__min'] or 0,
            }

            # Categories: union of assigned categories and categories the user has feedback in
            assigned_category_ids = set(UserCategoryAssignment.objects.filter(user=user).values_list('category_id', flat=True))
            categories_from_feedbacks = set(
                feedbacks_qs.filter(model__isnull=False).values_list('model__category_id', flat=True).distinct()
            )
            category_ids = list(assigned_category_ids.union(categories_from_feedbacks))

            # Fetch categories and models in bulk
            categories = list(Category.objects.filter(id__in=category_ids))
            models_qs = Model.objects.filter(category_id__in=category_ids).select_related('category')

            # Group models by category_id
            models_by_category = {}
            for m in models_qs:
                models_by_category.setdefault(m.category_id, []).append(m)

            # Precompute per-model aggregates in one query
            model_aggs = feedbacks_qs.filter(model__isnull=False).values('model').annotate(
                attempts_count=Count('id'),
                highest_score=Max('score'),
                average_score=Avg('score'),
                last_attempt=Max('submitted_at')
            )
            model_aggs_by_id = {row['model']: row for row in model_aggs}

            # Compute latest score per model in one pass over ordered feedbacks
            latest_by_model = {}
            for fb in feedbacks_qs.filter(model__isnull=False).order_by('-submitted_at').values('model_id', 'score', 'submitted_at'):
                mid = fb['model_id']
                if mid not in latest_by_model:
                    latest_by_model[mid] = {'latest_score': fb['score'], 'last_attempt': fb['submitted_at']}

            # Precompute per-category aggregates in one query
            category_aggs = feedbacks_qs.filter(model__isnull=False).values('model__category').annotate(
                attempts_count=Count('id'),
                average_score=Avg('score'),
                highest_score=Max('score'),
                lowest_score=Min('score'),
                last_attempt=Max('submitted_at'),
                models_attempted=Count('model', distinct=True)
            )
            category_aggs_by_id = {row['model__category']: row for row in category_aggs}

            # Build response structure with minimal additional queries
            category_stats = []
            for category in categories:
                cat_models = models_by_category.get(category.id, [])

                models_data = []
                for model in cat_models:
                    aggs = model_aggs_by_id.get(model.id)
                    latest = latest_by_model.get(model.id)
                    if aggs:
                        models_data.append({
                            'model_id': model.id,
                            'model_name': model.name,
                            'attempts_count': aggs['attempts_count'],
                            'latest_score': (latest['latest_score'] if latest else None),
                            'highest_score': aggs['highest_score'] or 0,
                            'last_attempt': (latest['last_attempt'] if latest else None),
                        })
                    else:
                        models_data.append({
                            'model_id': model.id,
                            'model_name': model.name,
                            'attempts_count': 0,
                            'latest_score': None,
                            'highest_score': 0,
                            'last_attempt': None,
                        })

                cat_aggs = category_aggs_by_id.get(category.id)
                if cat_aggs:
                    category_stats.append({
                        'category_id': category.id,
                        'category_name': category.name,
                        'attempts_count': cat_aggs['attempts_count'],
                        'average_score': cat_aggs['average_score'] or 0,
                        'highest_score': cat_aggs['highest_score'] or 0,
                        'lowest_score': cat_aggs['lowest_score'] or 0,
                        'last_attempt': cat_aggs['last_attempt'],
                        'models_count': len(cat_models),
                        'models_attempted': cat_aggs['models_attempted'],
                        'models': models_data,
                    })
                else:
                    category_stats.append({
                        'category_id': category.id,
                        'category_name': category.name,
                        'attempts_count': 0,
                        'average_score': 0,
                        'highest_score': 0,
                        'lowest_score': 0,
                        'last_attempt': None,
                        'models_count': len(cat_models),
                        'models_attempted': 0,
                        'models': models_data,
                    })

            # Sort: attempted first by last_attempt desc, then others by name
            with_attempts = [c for c in category_stats if c['attempts_count'] > 0]
            without_attempts = [c for c in category_stats if c['attempts_count'] == 0]
            with_attempts.sort(key=lambda x: x['last_attempt'], reverse=True)
            without_attempts.sort(key=lambda x: x['category_name'])
            category_stats = with_attempts + without_attempts

            # Most recent roleplay the user tried
            recent_score = feedbacks_qs.filter(model__isnull=False).order_by('-submitted_at').first()
            recent_roleplay = None
            if recent_score:
                recent_roleplay = {
                    'model_id': recent_score.model.id,
                    'model_name': recent_score.model.name,
                    'category_id': recent_score.model.category.id,
                    'category_name': recent_score.model.category.name,
                    'score': recent_score.score,
                    'timestamp': recent_score.submitted_at,
                }

            return Response({
                'user': {
                    'name': user.name,
                    'email': user.email,
                    'location_id': user.location_ghl_id,
                },
                'overall_stats': overall_stats,
                'category_stats': category_stats,
                'recent_roleplay': recent_roleplay,
            })

        except GHLUser.DoesNotExist:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['get'])
    def category_performance(self, request):
        """
        Detailed model-wise performance for a specific category.
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

            scores = Feedback.objects.filter(
                user=user,
                model__category=category
            ).select_related('model').order_by('-submitted_at')

            models_in_category = Model.objects.filter(category=category)

            model_performance = []
            for model in models_in_category:
                model_scores = scores.filter(model=model).order_by('-submitted_at')
                latest = model_scores.first()
                model_performance.append({
                    'model_id': model.id,
                    'model_name': model.name,
                    'attempts_count': model_scores.count(),
                    'latest_score': latest.score if latest else None,
                    'highest_score': model_scores.aggregate(Max('score'))['score__max'] if model_scores.exists() else 0,
                    'average_score': model_scores.aggregate(Avg('score'))['score__avg'] if model_scores.exists() else 0,
                    'last_attempt': latest.submitted_at if latest else None,
                    'has_attempt': model_scores.exists(),
                })

            model_performance.sort(key=lambda x: (not x['has_attempt'], x['model_name']))

            category_summary = {
                'total_attempts': scores.count(),
                'average_score': scores.aggregate(Avg('score'))['score__avg'] or 0,
                'highest_score': scores.aggregate(Max('score'))['score__max'] or 0,
                'lowest_score': scores.aggregate(Min('score'))['score__min'] or 0,
                'total_models': models_in_category.count(),
                'models_attempted': scores.values('model').distinct().count(),
            }

            return Response({
                'category': {
                    'id': category.id,
                    'name': category.name,
                    'description': category.description,
                },
                'summary': category_summary,
                'model_performance': model_performance,
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