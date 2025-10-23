import requests
from celery import shared_task
from account.models import GHLAuthCredentials
from django.conf import settings
import logging
from account.services import find_contact_by_email, update_ghl_contact, create_ghl_contact, find_contact_by_email, add_tag_to_contact, update_ghl_contact
from account.helpers import handle_user_webhook, sync_ghl_users

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
        
        handle_user_webhook(data, event_type)
        logger.info(f"Webhook {event_type} processed successfully")
    except Exception as e:
        logger.exception(f"Error handling user webhook event {event_type}: {e}")


@shared_task
def notify_category_assignment_task(user_email, user_first_name, user_last_name, user_phone, location_id, access_token, category_name, is_new_assignment=True):
    """
    Task to create/update contact in GHL with all user information and add/update "category added" tag
    """
    try:
        from account.services import create_ghl_contact, find_contact_by_email, add_tag_to_contact, update_ghl_contact
        
        TAG_NAME = "category added"
        
        print(f"🔍 Looking for existing contact for: {user_email}")
        
        # First, try to find existing contact
        existing_contact = find_contact_by_email(user_email, location_id, access_token)
        
        if existing_contact:
            # Contact exists - UPDATE it with latest information
            contact_id = existing_contact.get('id')
            print(f"✅ Found existing contact with ID: {contact_id}")
            print(f"🔄 Updating existing contact {contact_id}...")
            
            # Update contact with current user information
            updated_contact = update_ghl_contact(
                contact_id=contact_id,
                email=user_email,
                first_name=user_first_name,
                last_name=user_last_name,
                phone=user_phone,
                location_id=location_id,
                access_token=access_token
            )
            
            if updated_contact:
                print(f"✅ Contact updated successfully, ensuring tag exists...")
                
                # Simply add the tag - the API will handle if it already exists
                success = add_tag_to_contact(contact_id, TAG_NAME, location_id, access_token)
                if success:
                    print(f"✅ Contact updated and tag ensured: {user_email}")
                    return True
                else:
                    print(f"⚠️ Contact updated but tag operation failed: {user_email}")
                    return True  # Still return True since contact was updated
            else:
                print(f"❌ Failed to update contact: {user_email}")
                return False
                
        else:
            # Create new contact with all information and tag
            print(f"📝 No existing contact found, creating new one...")
            contact_data = create_ghl_contact(
                email=user_email,
                first_name=user_first_name,
                last_name=user_last_name,
                phone=user_phone,
                location_id=location_id,
                access_token=access_token,
                tags=[TAG_NAME]
            )
            
            if contact_data:
                print(f"✅ New contact created with all details and tag '{TAG_NAME}': {user_email}")
                return True
            else:
                print(f"❌ Failed to create contact: {user_email}")
                return False
                
    except Exception as e:
        print(f"❌ Error in notify_category_assignment_task: {e}")
        import traceback
        traceback.print_exc()
        return False


@shared_task
def update_user_contact_task(user_email, user_first_name, user_last_name, user_phone, location_id, access_token):
    """
    Task to update existing contact in GHL with latest user information
    """
    try:
        
        
        # Find existing contact
        existing_contact = find_contact_by_email(user_email, location_id, access_token)
        
        if existing_contact:
            contact_id = existing_contact.get('id')
            
            # Update contact with current user information
            updated_contact = update_ghl_contact(
                contact_id=contact_id,
                email=user_email,
                first_name=user_first_name,
                last_name=user_last_name,
                phone=user_phone,
                location_id=location_id,
                access_token=access_token
            )
            
            if updated_contact:
                print(f"✅ Contact information updated for: {user_email}")
                return True
            else:
                print(f"❌ Failed to update contact information for: {user_email}")
                return False
        else:
            print(f"⚠️ No existing contact found to update: {user_email}")
            return False
            
    except Exception as e:
        print(f"❌ Error in update_user_contact_task: {e}")
        return False