import requests
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware, now, is_naive
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
from .models import Contact, Opportunity, Pipeline, PipelineStage
import pytz

logger = logging.getLogger('data_management.helpers')

def sync_ghl_contacts_and_opportunities(location_id: str, access_token: str):
    """
    Sync contacts and opportunities from GHL for a specific location
    """
    try:
        logger.info(f"Starting sync for location: {location_id}")
        
        # Sync contacts
        contacts = get_all_ghl_contacts(access_token)
        if contacts:
            for contact_data in contacts:
                create_or_update_contact(contact_data)
            logger.info(f"Synced {len(contacts)} contacts for location {location_id}")
        
        # Sync opportunities
        opportunities = get_all_ghl_opportunities(access_token)
        if opportunities:
            for opportunity_data in opportunities:
                create_or_update_opportunity_from_sync(opportunity_data, access_token)
            logger.info(f"Synced {len(opportunities)} opportunities for location {location_id}")
            
        logger.info(f"Completed sync for location: {location_id}")
        
    except Exception as e:
        logger.error(f"Error syncing data for location {location_id}: {e}")
        raise

def get_all_ghl_contacts(access_token: str) -> List[Dict]:
    """
    Get all contacts from GHL API
    """
    url = "https://services.leadconnectorhq.com/contacts/"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-07-28"
    }
    
    all_contacts = []
    limit = 100
    offset = 0
    
    try:
        while True:
            params = {"limit": limit, "offset": offset}
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch contacts: {response.status_code} - {response.text}")
                break
                
            data = response.json()
            contacts = data.get("contacts", [])
            
            if not contacts:
                break
                
            all_contacts.extend(contacts)
            offset += limit
            
            # Break if we've gotten all contacts
            if len(contacts) < limit:
                break
                
    except Exception as e:
        logger.error(f"Error fetching contacts: {e}")
        
    return all_contacts

def get_all_ghl_opportunities(access_token: str) -> List[Dict]:
    """
    Get all opportunities from GHL API
    """
    url = "https://services.leadconnectorhq.com/opportunities/"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-07-28"
    }
    
    all_opportunities = []
    limit = 100
    offset = 0
    
    try:
        while True:
            params = {"limit": limit, "offset": offset}
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch opportunities: {response.status_code} - {response.text}")
                break
                
            data = response.json()
            opportunities = data.get("opportunities", [])
            
            if not opportunities:
                break
                
            all_opportunities.extend(opportunities)
            offset += limit
            
            # Break if we've gotten all opportunities
            if len(opportunities) < limit:
                break
                
    except Exception as e:
        logger.error(f"Error fetching opportunities: {e}")
        
    return all_opportunities

def create_or_update_contact(contact_data: Dict[str, Any]) -> Optional[Contact]:
    """
    Create or update a contact from GHL data
    """
    if not contact_data:
        logger.warning("No contact data provided")
        return None
        
    contact_id = contact_data.get("id")
    if not contact_id:
        logger.warning("No contact ID in data")
        return None
    
    try:
        # Parse and handle date
        date_added = _parse_date(contact_data.get("dateAdded"))
        
        # Prepare contact data
        contact_data_dict = {
            'contact_id': contact_id,
            'first_name': (contact_data.get("firstName") or "").strip()[:100],
            'last_name': (contact_data.get("lastName") or "").strip()[:100],
            'phone': (contact_data.get("phone") or "").strip()[:20],
            'email': (contact_data.get("email") or "").strip() or None,
            'address': _get_contact_address(contact_data),
            'country': (contact_data.get("country") or "").strip()[:10],
            'date_added': date_added or now(),
            'date_updated': now(),
            'tags': contact_data.get("tags", []),
            'source': (contact_data.get("source") or "ghl_api").strip()[:100],
        }
        
        # Generate full_name_lowercase
        full_name = f"{contact_data_dict['first_name']} {contact_data_dict['last_name']}"
        contact_data_dict['full_name_lowercase'] = full_name.lower().strip()
        
        # Create or update contact
        contact, created = Contact.objects.update_or_create(
            contact_id=contact_id,
            defaults=contact_data_dict
        )
        
        action = "created" if created else "updated"
        logger.info(f"Contact {contact_id} {action} successfully")
        return contact
        
    except Exception as e:
        logger.error(f"Error creating/updating contact {contact_id}: {e}")
        return None

def create_or_update_opportunity_from_sync(opportunity_data: Dict[str, Any], access_token: str) -> Optional[Opportunity]:
    """
    Create or update opportunity during sync (handles pipeline/stage creation)
    """
    if not opportunity_data:
        return None
        
    opportunity_id = opportunity_data.get("id")
    if not opportunity_id:
        return None
    
    try:
        # Get or create pipeline and stage
        pipeline_id = opportunity_data.get("pipelineId")
        stage_id = opportunity_data.get("pipelineStageId")
        
        pipeline = None
        stage = None
        
        if pipeline_id:
            pipeline, _ = Pipeline.objects.get_or_create(
                pipeline_id=pipeline_id,
                defaults={'name': f"Pipeline {pipeline_id}"}
            )
            
            # Update pipeline name if we have access token
            if access_token and not pipeline.name.startswith("Pipeline "):
                pipeline_info = get_ghl_pipeline(pipeline_id, access_token)
                if pipeline_info and pipeline_info.get("name"):
                    pipeline.name = pipeline_info["name"]
                    pipeline.save()
        
        if stage_id and pipeline:
            stage, _ = PipelineStage.objects.get_or_create(
                pipeline_stage_id=stage_id,
                pipeline=pipeline,
                defaults={
                    'name': f"Stage {stage_id}",
                    'stage_order': opportunity_data.get("stageOrder", 0)
                }
            )
        
        # Find or create contact
        contact_id = opportunity_data.get("contactId")
        contact = None
        if contact_id:
            contact = Contact.objects.filter(contact_id=contact_id).first()
            if not contact:
                # If contact doesn't exist, fetch it from GHL
                from account.services import get_ghl_contact
                contact_data = get_ghl_contact(contact_id, access_token)
                if contact_data and contact_data.get("contact"):
                    contact = create_or_update_contact(contact_data["contact"])
        
        if not contact:
            logger.warning(f"Contact {contact_id} not found for opportunity {opportunity_id}")
            return None
        
        # Parse dates
        created_timestamp = _parse_date(opportunity_data.get("createdAt")) or now()
        
        # Prepare opportunity data
        opportunity_data_dict = {
            'opportunity_id': opportunity_id,
            'contact': contact,
            'pipeline': pipeline,
            'current_stage': stage,
            'created_by_source': (opportunity_data.get("source") or "ghl_api").strip()[:50],
            'created_by_channel': "ghl_api",
            'source_id': (opportunity_data.get("source") or "").strip()[:255],
            'created_timestamp': created_timestamp,
            'value': _safe_float(opportunity_data.get("monetaryValue")),
            'assigned': (opportunity_data.get("assignedTo") or "").strip()[:150],
            'tags': str(opportunity_data.get("tags", [])),
            'engagement_score': _safe_int(opportunity_data.get("engagementScore")),
            'status': (opportunity_data.get("status") or "").strip()[:50] if opportunity_data.get("status") else None,
            'description': (opportunity_data.get("name") or "").strip(),
            'address': (opportunity_data.get("address") or "").strip(),
        }
        
        # Create or update opportunity
        opportunity, created = Opportunity.objects.update_or_create(
            opportunity_id=opportunity_id,
            defaults=opportunity_data_dict
        )
        
        action = "created" if created else "updated"
        logger.info(f"Opportunity {opportunity_id} {action} successfully")
        return opportunity
        
    except Exception as e:
        logger.error(f"Error creating/updating opportunity {opportunity_id}: {e}")
        return None

def get_ghl_pipeline(pipeline_id: str, access_token: str) -> Optional[Dict]:
    """
    Get pipeline details from GHL
    """
    url = f"https://services.leadconnectorhq.com/pipelines/{pipeline_id}"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-07-28"
    }
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.error(f"Error fetching pipeline {pipeline_id}: {e}")
    
    return None

def _parse_date(date_str: str) -> Optional[datetime]:
    """Parse date string and return timezone-aware datetime"""
    if not date_str:
        return None

    try:
        parsed_date = parse_datetime(date_str)
        if parsed_date:
            if is_naive(parsed_date):
                parsed_date = make_aware(parsed_date)
            return parsed_date
    except Exception:
        pass

    return None

def _get_contact_address(contact_data: Dict) -> str:
    """Extract address from contact data"""
    address_parts = []
    
    # Check for different address structures
    if contact_data.get("address1"):
        address_parts.append(contact_data["address1"])
    if contact_data.get("city"):
        address_parts.append(contact_data["city"])
    if contact_data.get("state"):
        address_parts.append(contact_data["state"])
    if contact_data.get("zip"):
        address_parts.append(contact_data["zip"])
    if contact_data.get("country"):
        address_parts.append(contact_data["country"])
    
    return ", ".join(filter(None, address_parts))[:255]

def _safe_float(value: Any) -> Optional[float]:
    """Safely convert value to float"""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None

def _safe_int(value: Any) -> int:
    """Safely convert value to int"""
    if value is None or value == "":
        return 0
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return 0