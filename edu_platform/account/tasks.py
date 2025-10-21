import requests
from celery import shared_task
from account.models import GHLAuthCredentials
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

@shared_task
def make_api_for_ghl():
    """
    Task to refresh GHL access tokens using refresh token
    """
    logger.info("Refreshing GHL tokens...")

    try:
        credentials_list = GHLAuthCredentials.objects.all()

        for credentials in credentials_list:
            if not credentials.refresh_token:
                continue

            response = requests.post(
                'https://services.leadconnectorhq.com/oauth/token',
                data={
                    'grant_type': 'refresh_token',
                    'client_id': settings.GHL_CLIENT_ID,
                    'client_secret': settings.GHL_CLIENT_SECRET,
                    'refresh_token': credentials.refresh_token
                }
            )

            if response.status_code == 200:
                new_tokens = response.json()
                logger.info(f"Tokens refreshed for location: {credentials.location_id}")

                GHLAuthCredentials.objects.filter(location_id=credentials.location_id).update(
                    access_token=new_tokens.get("access_token"),
                    refresh_token=new_tokens.get("refresh_token"),
                    expires_in=new_tokens.get("expires_in"),
                    scope=new_tokens.get("scope"),
                    user_type=new_tokens.get("userType"),
                    company_id=new_tokens.get("companyId"),
                    user_id=new_tokens.get("userId"),
                )
            else:
                logger.error(f"Failed to refresh tokens for location {credentials.location_id}: {response.status_code}")

    except Exception as e:
        logger.exception(f"Error in token refresh task: {e}")


@shared_task
def sync_ghl_users_task(location_id, access_token):
    """
    Task to sync users during onboarding
    """
    logger.info(f"Starting user sync for location: {location_id}")
    try:
        from account.helpers import sync_ghl_users
        users_synced = sync_ghl_users(location_id, access_token)
        logger.info(f"Successfully synced {users_synced} users for location: {location_id}")
        return users_synced
    except Exception as e:
        logger.exception(f"Error syncing users for location {location_id}: {e}")
        return 0


@shared_task
def manual_refresh_users_task(location_id):
    """
    Task for manual user refresh from frontend
    """
    logger.info(f"Manual refresh started for location: {location_id}")
    try:
        credentials = GHLAuthCredentials.objects.get(location_id=location_id)
        from account.helpers import sync_ghl_users
        users_synced = sync_ghl_users(location_id, credentials.access_token)
        logger.info(f"Manual refresh completed: {users_synced} users synced")
        return users_synced
    except Exception as e:
        logger.exception(f"Error in manual refresh for location {location_id}: {e}")
        return 0


@shared_task
def handle_user_webhook_event(data, event_type):
    """
    Process user webhook events asynchronously
    """
    try:
        from account.helpers import handle_user_webhook
        handle_user_webhook(data, event_type)
        logger.info(f"Webhook {event_type} processed successfully")
    except Exception as e:
        logger.exception(f"Error handling user webhook event {event_type}: {e}")
