#!/usr/bin/env python3
import os
import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from fastmcp import FastMCP
from icalendar import Calendar, Event
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import pytz
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# In-memory storage (replace with a database in production)
scheduling_requests: Dict[str, dict] = {}

# Email configuration (configure these in your .env file)
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')

# Initialize FastMCP

mcp = FastMCP("Scheduling MCP Server")

def generate_available_slots() -> List[datetime]:
    """Generate sample available time slots for the next 7 days."""
    now = datetime.now(pytz.utc)
    slots = []
    for day in range(1, 8):  # Next 7 days
        for hour in range(9, 17):  # Business hours 9 AM to 5 PM
            # Create timezone-aware datetime
            slot = (now + timedelta(days=day)).replace(
                hour=hour, minute=0, second=0, microsecond=0
            )
            slots.append(slot)
    return slots

def send_email(recipient: str, subject: str, body: str, ical_attachment: bytes = None) -> bool:
    """Send an email with optional iCalendar attachment."""
    if not all([SMTP_SERVER, EMAIL_ADDRESS, EMAIL_PASSWORD]):
        print("Email not configured. Set SMTP_SERVER, EMAIL_ADDRESS, and EMAIL_PASSWORD in .env")
        return False
    
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = recipient
        msg['Subject'] = subject
        
        # Attach text body
        msg.attach(MIMEText(body, 'plain'))
        
        # Attach iCalendar if provided
        if ical_attachment:
            ical_attach = MIMEText(ical_attachment.decode('utf-8'), 'calendar;method=REQUEST')
            ical_attach.add_header('Content-Disposition', 'attachment; filename="meeting.ics"')
            msg.attach(ical_attach)
        
        # Send email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
            
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

@mcp.tool(description="Send available times to target user to attempt to schedule a meeting")
def send_scheduling_email(target_email: str) -> dict:
    """
    Send available meeting times to the target user for scheduling.
    
    Args:
        target_email: Email address of the recipient
        
    Returns:
        dict: Status of the operation and request ID
    """
    request_id = str(uuid.uuid4())
    available_slots = generate_available_slots()
    
    # Store the scheduling request
    scheduling_requests[request_id] = {
        'target_email': target_email,
        'available_slots': available_slots,
        'status': 'pending',
        'created_at': datetime.now(pytz.utc).isoformat()
    }
    
    # Format available slots for email
    slots_str = "\n".join(
        f"{i+1}. {slot.strftime('%A, %B %d, %Y at %I:%M %p %Z')}" 
        for i, slot in enumerate(available_slots[:10])  # Show first 10 slots
    )
    
    # Send email
    subject = "Available Meeting Times"
    body = f"""Hello,\n\nHere are some available times for our meeting. Please reply with your preferred time slot number.\n\n{slots_str}\n\nBest regards,\nScheduling System"""
    
    email_sent = send_email(target_email, subject, body)
    
    if email_sent:
        return {
            'status': 'success',
            'message': 'Scheduling email sent successfully',
            'request_id': request_id,
            'available_slots_count': len(available_slots)
        }
    else:
        return {
            'status': 'error',
            'message': 'Failed to send scheduling email',
            'request_id': request_id
        }

@mcp.tool(description="Reply to a scheduling email with the selected time")
def reply_scheduling_email(request_id: str, selected_slot_index: int) -> dict:
    """
    Process the selected time slot and confirm the meeting.
    
    Args:
        request_id: The scheduling request ID
        selected_slot_index: Index of the selected time slot (0-based)
        
    Returns:
        dict: Status of the operation and meeting details
    """
    if request_id not in scheduling_requests:
        return {'status': 'error', 'message': 'Invalid request ID'}
    
    request = scheduling_requests[request_id]
    
    try:
        selected_slot = request['available_slots'][selected_slot_index]
    except IndexError:
        return {'status': 'error', 'message': 'Invalid time slot index'}
    
    # Update the request with the selected time
    request['selected_slot'] = selected_slot.isoformat()
    request['status'] = 'scheduled'
    
    # Create calendar event
    cal = Calendar()
    cal.add('prodid', '-//Meeting Scheduler//example.com//')
    cal.add('version', '2.0')
    
    event = Event()
    event.add('summary', 'Scheduled Meeting')
    event.add('dtstart', selected_slot)
    event.add('dtend', selected_slot + timedelta(hours=1))
    event.add('dtstamp', datetime.now(pytz.utc))
    event['uid'] = f'{request_id}@example.com'
    
    cal.add_component(event)
    ical_content = cal.to_ical()
    
    # Send confirmation email
    subject = "Meeting Confirmed"
    body = f"""Hello,\n\nYour meeting has been confirmed for:\n\n{selected_slot.strftime('%A, %B %d, %Y at %I:%M %p %Z')}\n\nA calendar invite has been attached.\n\nBest regards,\nScheduling System"""
    
    email_sent = send_email(
        request['target_email'],
        subject,
        body,
        ical_content
    )
    
    if email_sent:
        # Save to calendar
        save_result = save_scheduled_meetup({
            'request_id': request_id,
            'email': request['target_email'],
            'start_time': selected_slot.isoformat(),
            'end_time': (selected_slot + timedelta(hours=1)).isoformat(),
            'title': 'Scheduled Meeting'
        })
        
        return {
            'status': 'success',
            'message': 'Meeting scheduled successfully',
            'meeting_time': selected_slot.isoformat(),
            'calendar_saved': save_result.get('success', False)
        }
    else:
        return {
            'status': 'error',
            'message': 'Failed to send confirmation email',
            'meeting_time': selected_slot.isoformat()
        }

@mcp.tool(description="Save the scheduled meeting to the calendar")
def save_scheduled_meetup(meeting_data: dict) -> dict:
    """
    Save the scheduled meeting to the calendar.
    
    Args:
        meeting_data: Dictionary containing meeting details
            - request_id: The scheduling request ID
            - email: Attendee's email
            - start_time: Meeting start time (ISO format)
            - end_time: Meeting end time (ISO format)
            - title: Meeting title
    
    Returns:
        dict: Status of the operation
    """
    try:
        # In a real implementation, you would save to a calendar system here
        # For example, Google Calendar API, Outlook API, or a database
        
        # For demonstration, we'll just log the meeting
        print(f"Saving meeting to calendar: {meeting_data}")
        
        # Update the scheduling request
        if meeting_data.get('request_id') in scheduling_requests:
            scheduling_requests[meeting_data['request_id']]['calendar_saved'] = True
        
        return {
            'success': True,
            'message': 'Meeting saved to calendar',
            'meeting_data': meeting_data
        }
    except Exception as e:
        return {
            'success': False,
            'message': f'Failed to save meeting to calendar: {str(e)}',
            'meeting_data': meeting_data
        }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = "0.0.0.0"
    
    print(f"Starting FastMCP server on {host}:{port}")
    
    # Check if email is configured
    if not all([SMTP_SERVER, EMAIL_ADDRESS, EMAIL_PASSWORD]):
        print("\nWARNING: Email not fully configured. Set the following environment variables:")
        print("  - SMTP_SERVER (e.g., smtp.gmail.com)")
        print("  - EMAIL_ADDRESS (your email address)")
        print("  - EMAIL_PASSWORD (your email password or app password)\n")
    
    mcp.run(
        transport="http",
        host=host,
        port=port
    )
