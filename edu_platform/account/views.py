from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import redirect
from decouple import config
import requests
from .models import GHLAuthCredentials, WebhookLog, GHLUser
from .tasks import sync_ghl_users_task, manual_refresh_users_task, handle_user_webhook_event
from .services import get_location_name
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .serializers import GHLUserSerializer
from roleplay.models import UserCategoryAssignment

GHL_CLIENT_ID = config("GHL_CLIENT_ID")
GHL_CLIENT_SECRET = config("GHL_CLIENT_SECRET")
GHL_REDIRECTED_URI = config("GHL_REDIRECTED_URI")
TOKEN_URL = "https://services.leadconnectorhq.com/oauth/token"

class GHLAuthConnectView(APIView):
    def get(self, request):
        scope = config("SCOPE", "users.readonly users.write locations.readonly")
        auth_url = (
            "https://marketplace.leadconnectorhq.com/oauth/chooselocation?"
            f"response_type=code&"
            f"redirect_uri={GHL_REDIRECTED_URI}&"
            f"client_id={GHL_CLIENT_ID}&"
            f"scope={scope}"
        )
        return redirect(auth_url)

class GHLCallbackView(APIView):
    def get(self, request):
        code = request.GET.get('code')
        
        if not code:
            return Response(
                {"error": "Authorization code not received from OAuth"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return redirect(f'{config("BASE_URI")}/accounts/auth/tokens?code={code}')

class GHLTokensView(APIView):
    def get(self, request):
        authorization_code = request.GET.get("code")

        if not authorization_code:
            return Response(
                {"error": "Authorization code not found"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        data = {
            "grant_type": "authorization_code",
            "client_id": GHL_CLIENT_ID,
            "client_secret": GHL_CLIENT_SECRET,
            "redirect_uri": GHL_REDIRECTED_URI,
            "code": authorization_code,
        }

        response = requests.post(TOKEN_URL, data=data)

        try:
            response_data = response.json()
            
            if response.status_code != 200:
                return Response(
                    {"error": response_data.get("error", "Authentication failed")},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get location details
            location_name, timezone = get_location_name(
                location_id=response_data.get("locationId"), 
                access_token=response_data.get('access_token')
            )

            # Save credentials
            obj, created = GHLAuthCredentials.objects.update_or_create(
                location_id=response_data.get("locationId"),
                defaults={
                    "access_token": response_data.get("access_token"),
                    "refresh_token": response_data.get("refresh_token"),
                    "expires_in": response_data.get("expires_in"),
                    "scope": response_data.get("scope"),
                    "user_type": response_data.get("userType"),
                    "company_id": response_data.get("companyId"),
                    "user_id": response_data.get("userId"),
                    "location_name": location_name,
                    "timezone": timezone or "UTC"
                }
            )

            # FIX: Use direct function call instead of Celery task
            from .helpers import sync_ghl_users
            users_synced = sync_ghl_users(
                response_data.get("locationId"),
                response_data.get("access_token")
            )

            return Response({
                "message": "Authentication successful",
                "location_id": response_data.get("locationId"),
                "location_name": location_name,
                "users_synced": users_synced,
                "token_stored": True
            })
            
        except requests.exceptions.JSONDecodeError:
            return Response({
                "error": "Invalid JSON response from API",
                "status_code": response.status_code,
                "response_text": response.text[:500]
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ManualRefreshUsersView(APIView):
    """API for manual user refresh from frontend"""
    def post(self, request):
        location_id = request.data.get('location_id')
        
        if not location_id:
            return Response(
                {"error": "location_id is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            credentials = GHLAuthCredentials.objects.get(location_id=location_id)
            # FIX: Use direct function call instead of Celery task
            from .helpers import sync_ghl_users
            users_synced = sync_ghl_users(location_id, credentials.access_token)
            
            return Response({
                "message": "User refresh completed",
                "users_synced": users_synced,
                "location_id": location_id
            })
            
        except GHLAuthCredentials.DoesNotExist:
            return Response(
                {"error": "Location not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
class GetUsersView(APIView):
    """API to get all users for a location"""
    def get(self, request):
        location_id = request.GET.get('location_id')
        
        if not location_id:
            return Response(
                {"error": "location_id is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            users = GHLUser.objects.filter(location__location_id=location_id)
            users_data = []
            
            for user in users:
                users_data.append({
                    'user_id': user.user_id,
                    'name': user.name,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'email': user.email,
                    'phone': user.phone,
                    'role': user.role,
                    'status': user.status,
                    'created_at': user.created_at
                })
            
            return Response({
                "location_id": location_id,
                "users_count": len(users_data),
                "users": users_data
            })
            
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

@method_decorator(csrf_exempt, name='dispatch')
class GHLWebhookView(APIView):
    def post(self, request):
        try:
            data = request.data
            print("Webhook data:", data)
            
            # Log webhook
            WebhookLog.objects.create(data=data)
            
            event_type = data.get("type")
            
            # FIX: Use direct function call instead of Celery task
            if event_type in ["UserCreated", "UserUpdated", "UserDeleted"]:
                from .helpers import handle_user_webhook
                handle_user_webhook(data, event_type)
            
            return Response({"message": "Webhook received"}, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"Webhook handler error: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

class GetUsersView(APIView):
    """API to get all users for a location"""
    def get(self, request):
        location_id = request.GET.get('location_id')
        
        users = GHLUser.objects.all()
        if location_id:
            users = users.filter(location__location_id=location_id)
        
        serializer = GHLUserSerializer(users, many=True)
        return Response(serializer.data)