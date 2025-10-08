from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, ModelViewSet, GHLUserViewSet, UserAccessViewSet

router = DefaultRouter()
router.register(r'categories', CategoryViewSet)
router.register(r'models', ModelViewSet)
router.register(r'users', GHLUserViewSet, basename='ghl-users')
router.register(r'user-access', UserAccessViewSet, basename='user-access')

urlpatterns = [
    path('', include(router.urls)),
]