from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework import serializers
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Avg, Count, Q, Max, Min
from datetime import datetime, timezone
from .models import Category, Model, UserCategoryAssignment, Feedback
from account.models import GHLUser
from .serializers import (
    CategorySerializer, ModelSerializer, 
    GHLUserSerializer, FeedbackSerializer,
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
    
    @action(detail=False, methods=['post'])
    def assign_default_categories(self, request):
        """
        Assign default categories to all active users
        """
        default_categories = Category.objects.filter(is_default=True)
        active_users = GHLUser.objects.filter(status='active')
        
        assignments_created = 0
        for user in active_users:
            for category in default_categories:
                # Check if assignment already exists
                if not UserCategoryAssignment.objects.filter(user=user, category=category).exists():
                    UserCategoryAssignment.objects.create(user=user, category=category)
                    assignments_created += 1
        
        return Response({
            "message": f"Assigned {len(default_categories)} default categories to {active_users.count()} users",
            "assignments_created": assignments_created
        })

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

            # Get all feedback history for models
            feedbacks_by_model = {}
            for fb in feedbacks_qs.filter(model__isnull=False).order_by('-submitted_at'):
                model_id = fb.model_id
                if model_id not in feedbacks_by_model:
                    feedbacks_by_model[model_id] = []
                feedbacks_by_model[model_id].append({
                    'model_id': fb.model_id,
                    'model_name': fb.model.name,
                    'score': fb.score,
                    'strengths': fb.strengths,
                    'improvements': fb.improvements,
                    'submitted_at': fb.submitted_at
                })

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
                    
                    # Get attempt history for this model
                    attempt_history = feedbacks_by_model.get(model.id, [])
                    
                    model_data = {
                        'model_id': model.id,
                        'model_name': model.name,
                        'attempts_count': aggs['attempts_count'] if aggs else 0,
                        'latest_score': (latest['latest_score'] if latest else None),
                        'highest_score': aggs['highest_score'] if aggs else 0,
                        'last_attempt': (latest['last_attempt'] if latest else None),
                        'models_attempt_history': attempt_history,
                        'min_score_to_pass': model.min_score_to_pass,
                        'min_attempts_required': model.min_attempts_required
                    }
                    models_data.append(model_data)

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



class AdminReportsViewSet(viewsets.ViewSet):
    """API for admin dashboard showing reports for all users"""
    
    @action(detail=False, methods=['get'])
    def all_users_performance(self, request):
        """
        Get performance data for all users in a location or all locations
        """
        location_id = request.query_params.get('location_id')
        
        # Build base queryset
        users_qs = GHLUser.objects.filter(status='active')
        if location_id:
            users_qs = users_qs.filter(location_ghl_id=location_id)
        
        users_data = []
        
        for user in users_qs.select_related('location'):
            # Get user's feedback data
            feedbacks_qs = Feedback.objects.filter(user=user).select_related('model', 'model__category')
            
            # Overall stats
            overall_stats = {
                'total_feedbacks': feedbacks_qs.count(),
                'total_scores': feedbacks_qs.count(),
                'average_score': feedbacks_qs.aggregate(Avg('score'))['score__avg'] or 0,
                'highest_score': feedbacks_qs.aggregate(Max('score'))['score__max'] or 0,
                'lowest_score': feedbacks_qs.aggregate(Min('score'))['score__min'] or 0,
            }
            
            # Category stats
            assigned_category_ids = set(
                UserCategoryAssignment.objects.filter(user=user).values_list('category_id', flat=True)
            )
            categories_from_feedbacks = set(
                feedbacks_qs.filter(model__isnull=False)
                .values_list('model__category_id', flat=True)
                .distinct()
            )
            category_ids = list(assigned_category_ids.union(categories_from_feedbacks))
            
            categories = Category.objects.filter(id__in=category_ids)
            category_stats = []
            
            for category in categories:
                category_feedbacks = feedbacks_qs.filter(model__category=category)
                category_aggs = category_feedbacks.aggregate(
                    attempts_count=Count('id'),
                    average_score=Avg('score'),
                    highest_score=Max('score'),
                    lowest_score=Min('score'),
                    last_attempt=Max('submitted_at'),
                    models_attempted=Count('model', distinct=True)
                )
                
                # Get models for this category
                models_in_category = Model.objects.filter(category=category)
                models_data = []
                
                for model in models_in_category:
                    model_feedbacks = feedbacks_qs.filter(model=model).order_by('-submitted_at')
                    model_aggs = model_feedbacks.aggregate(
                        attempts_count=Count('id'),
                        highest_score=Max('score'),
                        average_score=Avg('score'),
                        last_attempt=Max('submitted_at')
                    )
                    
                    # Get latest score
                    latest_feedback = model_feedbacks.first()
                    latest_score = latest_feedback.score if latest_feedback else None
                    
                    # Get attempt history for this model
                    attempt_history = []
                    for feedback in model_feedbacks:
                        attempt_history.append({
                            'model_id': feedback.model.id,
                            'model_name': feedback.model.name,
                            'score': feedback.score,
                            'strengths': feedback.strengths,
                            'improvements': feedback.improvements,
                            'submitted_at': feedback.submitted_at
                        })
                    
                    models_data.append({
                        'model_id': model.id,
                        'model_name': model.name,
                        'attempts_count': model_aggs['attempts_count'] or 0,
                        'latest_score': latest_score,
                        'highest_score': model_aggs['highest_score'] or 0,
                        'average_score': model_aggs['average_score'] or 0,
                        'last_attempt': model_aggs['last_attempt'],
                        'min_score_to_pass': model.min_score_to_pass,
                        'min_attempts_required': model.min_attempts_required,
                        'models_attempt_history': attempt_history
                    })
                
                category_stats.append({
                    'category_id': category.id,
                    'category_name': category.name,
                    'attempts_count': category_aggs['attempts_count'] or 0,
                    'average_score': category_aggs['average_score'] or 0,
                    'highest_score': category_aggs['highest_score'] or 0,
                    'lowest_score': category_aggs['lowest_score'] or 0,
                    'last_attempt': category_aggs['last_attempt'],
                    'models_attempted': category_aggs['models_attempted'] or 0,
                    'models': models_data
                })
            
            # Most recent roleplay
            recent_feedback = feedbacks_qs.filter(model__isnull=False).order_by('-submitted_at').first()
            recent_roleplay = None
            if recent_feedback:
                recent_roleplay = {
                    'model_id': recent_feedback.model.id,
                    'model_name': recent_feedback.model.name,
                    'category_id': recent_feedback.model.category.id,
                    'category_name': recent_feedback.model.category.name,
                    'score': recent_feedback.score,
                    'timestamp': recent_feedback.submitted_at,
                }
            
            # Calculate completion status
            assigned_categories_count = UserCategoryAssignment.objects.filter(user=user).count()
            completed_categories_count = len([
                cat for cat in category_stats 
                if cat['attempts_count'] > 0
            ])
            
            users_data.append({
                'user': {
                    'user_id': user.user_id,
                    'name': user.name,
                    'email': user.email,
                    'location_id': user.location_ghl_id,
                    'location_name': user.location.location_name if user.location else 'Unknown',
                },
                'overall_stats': overall_stats,
                'category_stats': category_stats,
                'recent_roleplay': recent_roleplay,
                'completion_status': {
                    'assigned_categories': assigned_categories_count,
                    'completed_categories': completed_categories_count,
                    'completion_rate': round(
                        (completed_categories_count / assigned_categories_count * 100) 
                        if assigned_categories_count > 0 else 0, 
                        2
                    )
                }
            })
        
        # Sort users by completion rate (highest first) then by name
        users_data.sort(key=lambda x: (
            -x['completion_status']['completion_rate'],
            x['user']['name'].lower()
        ))
        
        # Calculate location-wide stats
        location_stats = {
            'total_users': len(users_data),
            'total_feedbacks': sum(user['overall_stats']['total_feedbacks'] for user in users_data),
            'average_score_all_users': round(
                sum(user['overall_stats']['average_score'] for user in users_data) / len(users_data) 
                if users_data else 0, 
                2
            ),
            'average_completion_rate': round(
                sum(user['completion_status']['completion_rate'] for user in users_data) / len(users_data) 
                if users_data else 0, 
                2
            ),
        }
        
        return Response({
            'location_stats': location_stats,
            'users': users_data,
        })
    
    @action(detail=False, methods=['get'])
    def location_summary(self, request):
        """
        Get summary statistics for locations
        """
        location_id = request.query_params.get('location_id')
        
        locations_qs = GHLUser.objects.filter(status='active')
        if location_id:
            locations_qs = locations_qs.filter(location_ghl_id=location_id)
        
        # Group by location
        from django.db.models import Count, Avg
        location_stats = locations_qs.values(
            'location_ghl_id', 'location__location_name'
        ).annotate(
            user_count=Count('user_id'),
            total_feedbacks=Count('feedbacks'),
            avg_score=Avg('feedbacks__score')
        ).order_by('-user_count')
        
        return Response(list(location_stats))