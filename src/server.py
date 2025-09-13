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

@mcp.prompt("send_available_times")
def send_available_times(name: str, email: str) -> str:
    """
    Gets the availability of the user and sends it to another user
    """

    prompt = "Find all my available times next week and send them to " + email + " in the following format:\n\n" \
        "Hey " + name + "!\n\n" \
        "Would love to meet you soon! Here are my available times over the next week:\n\n" \
        "<available times>\n\n" \
        "Best regards,\n" \
        "<Your Name>"

    return prompt


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = "0.0.0.0"
    
    print(f"Starting Scheduling server on {host}:{port}")
    
    mcp.run(
        transport="http",
        host=host,
        port=port
    )
