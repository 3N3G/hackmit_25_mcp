"""
Google Calendar Integration Module

This module provides functionality to interact with Google Calendar API,
including fetching free/busy slots and creating events.
"""

from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Any, Optional
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import os
import logging
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Constants
MINIMUM_INTERVAL_MINUTES = 30

class GoogleCalendarService:
    """Service class for Google Calendar operations."""
    
    def __init__(self, access_token: str):
        """Initialize with user's OAuth2 access token."""
        self.creds = Credentials(
            token=access_token,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=os.getenv('GOOGLE_CLIENT_ID'),
            client_secret=os.getenv('GOOGLE_CLIENT_SECRET')
        )
        self.service = build('calendar', 'v3', credentials=self.creds)

    @staticmethod
    def merge_intervals(intervals: List[Tuple[datetime, datetime]]) -> List[Tuple[datetime, datetime]]:
        """Merge overlapping or adjacent time intervals."""
        if not intervals:
            return []

        # Sort intervals by start time
        intervals.sort(key=lambda x: x[0])

        merged = []
        current_interval = intervals[0]

        for next_start, next_end in intervals[1:]:
            current_start, current_end = current_interval
            
            # If current interval overlaps or is adjacent to the next one
            if current_end + timedelta(minutes=MINIMUM_INTERVAL_MINUTES) >= next_start:
                # Merge them
                current_interval = (
                    min(current_start, next_start),
                    max(current_end, next_end)
                )
            else:
                merged.append(current_interval)
                current_interval = (next_start, next_end)
        
        merged.append(current_interval)
        return merged

    @staticmethod
    def get_free_intervals(busy_intervals: List[Tuple[datetime, datetime]], 
                         start_time: datetime, 
                         end_time: datetime) -> List[Tuple[datetime, datetime]]:
        """Calculate free time slots between busy intervals."""
        if not busy_intervals:
            return [(start_time, end_time)]

        merged = GoogleCalendarService.merge_intervals(busy_intervals)
        free_intervals = []
        last_end = start_time

        for busy_start, busy_end in merged:
            if last_end < busy_start:
                free_intervals.append((last_end, busy_start))
            last_end = max(last_end, busy_end)
        
        if last_end < end_time:
            free_intervals.append((last_end, end_time))
            
        return free_intervals

    async def get_free_slots(self, days_ahead: int = 7) -> List[Dict[str, str]]:
        """
        Get free time slots for the next N days.
        
        Args:
            days_ahead: Number of days to look ahead for free slots
            
        Returns:
            List of dictionaries with 'start' and 'end' ISO format datetime strings
        """
        try:
            now = datetime.utcnow()
            end = now + timedelta(days=days_ahead)
            
            # Get list of calendars
            calendars_result = self.service.calendarList().list().execute()
            calendar_ids = [cal['id'] for cal in calendars_result.get('items', [])]
            
            # Prepare free/busy request
            free_busy_request = {
                "timeMin": now.isoformat() + 'Z',
                "timeMax": end.isoformat() + 'Z',
                "items": [{"id": cal_id} for cal_id in calendar_ids]
            }
            
            # Get busy intervals
            free_busy = self.service.freebusy().query(body=free_busy_request).execute()
            
            # Process busy intervals
            busy_intervals = []
            for cal_data in free_busy.get('calendars', {}).values():
                for busy in cal_data.get('busy', []):
                    busy_intervals.append((
                        datetime.fromisoformat(busy['start'].replace('Z', '+00:00')),
                        datetime.fromisoformat(busy['end'].replace('Z', '+00:00'))
                    ))
            
            # Get free intervals
            free_intervals = self.get_free_intervals(busy_intervals, now, end)
            
            # Format response
            return [
                {
                    'start': start.isoformat(),
                    'end': end.isoformat()
                }
                for start, end in free_intervals
                if (end - start).total_seconds() >= MINIMUM_INTERVAL_MINUTES * 60
            ]
            
        except Exception as e:
            logger.error(f"Error fetching free slots: {str(e)}")
            raise

    async def create_event(self, summary: str, start_time: datetime, 
                         end_time: datetime, **kwargs) -> Dict[str, Any]:
        """
        Create a new calendar event.
        
        Args:
            summary: Event title
            start_time: Event start time
            end_time: Event end time
            **kwargs: Additional event properties
            
        Returns:
            Created event data
        """
        try:
            event = {
                'summary': summary,
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': 'UTC',
                },
                **kwargs
            }
            
            created_event = self.service.events().insert(
                calendarId='primary',
                body=event
            ).execute()
            
            logger.info(f"Created event: {created_event.get('htmlLink')}")
            return created_event
            
        except Exception as e:
            logger.error(f"Error creating event: {str(e)}")
            raise

class GooglePeopleService:
    """Service class for Google People API operations."""
    
    def __init__(self, access_token: str):
        """Initialize with user's OAuth2 access token."""
        self.creds = Credentials(
            token=access_token,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=os.getenv('GOOGLE_CLIENT_ID'),
            client_secret=os.getenv('GOOGLE_CLIENT_SECRET')
        )
        self.service = build('people', 'v1', credentials=self.creds)

    async def get_contacts(self) -> List[Dict[str, str]]:
        """
        Get user's contacts with names, emails, and phone numbers.
        
        Returns:
            List of contact dictionaries with id, name, email, and phone
        """
        try:
            contacts = []
            page_token = None
            
            while True:
                results = self.service.people().connections().list(
                    resourceName='people/me',
                    pageSize=1000,
                    personFields='names,emailAddresses,phoneNumbers',
                    pageToken=page_token
                ).execute()
                
                connections = results.get('connections', [])
                
                for person in connections:
                    contact = {
                        'id': person.get('resourceName', ''),
                        'name': person.get('names', [{}])[0].get('displayName', ''),
                        'email': person.get('emailAddresses', [{}])[0].get('value', ''),
                        'phone': person.get('phoneNumbers', [{}])[0].get('value', '')
                    }
                    contacts.append(contact)
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
                    
            return contacts
            
        except Exception as e:
            logger.error(f"Error fetching contacts: {str(e)}")
            raise
