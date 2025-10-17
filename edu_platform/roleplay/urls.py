from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, ModelViewSet, GHLUserViewSet, UserAccessViewSet, FeedbackViewSet, UserPerformanceViewSet

router = DefaultRouter()
router.register(r'categories', CategoryViewSet)
router.register(r'models', ModelViewSet)
router.register(r'users', GHLUserViewSet, basename='ghl-users')
router.register(r'user-access', UserAccessViewSet, basename='user-access')
router.register(r'feedback', FeedbackViewSet, basename='feedback')
# router.register(r'scores', RoleplayScoreViewSet, basename='scores')
router.register(r'performance', UserPerformanceViewSet, basename='performance')

urlpatterns = [
    path('', include(router.urls)),
]