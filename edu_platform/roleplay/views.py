from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Category, Model, UserCategoryAssignment
from account.models import GHLUser
from .serializers import (
    CategorySerializer, ModelSerializer, 
    GHLUserSerializer  # Removed UserCategoryAssignmentSerializer
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
                    'email': user.email
                },
                'categories': categories_data
            })
            
        except GHLUser.DoesNotExist:
            return Response(
                {"error": "User not found or inactive"}, 
                status=status.HTTP_404_NOT_FOUND
            )