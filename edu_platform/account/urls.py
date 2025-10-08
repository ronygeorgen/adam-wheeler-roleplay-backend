from django.urls import path
from .views import (
    GHLAuthConnectView, GHLCallbackView, GHLTokensView, 
    GHLWebhookView, ManualRefreshUsersView, GetUsersView
)

urlpatterns = [
    path('connect/', GHLAuthConnectView.as_view(), name='ghl-auth-connect'),
    path('callback/', GHLCallbackView.as_view(), name='ghl-auth-callback'),
    path('tokens/', GHLTokensView.as_view(), name='ghl-auth-tokens'),
    path('webhook/', GHLWebhookView.as_view(), name='ghl-webhook'),
    path('refresh-users/', ManualRefreshUsersView.as_view(), name='ghl-refresh-users'),
    path('get-users/', GetUsersView.as_view(), name='ghl-get-users'),
]