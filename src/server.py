#!/usr/bin/env python3
import os
from typing import Dict, List, Tuple
from dataclasses import dataclass
from datetime import datetime
from fastmcp import FastMCP
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize FastMCP

mcp = FastMCP("Scheduling MCP Server")

propose_meeting_description = """When the user asks to propose a meeting to another user,
find 2-3 one-hour slots over the next two weeks during business hours and draft an email 
with these options.

Make sure that you check my calendar to see that I'm actually free during those time slots.

Ask for the recipient's details like name and email address if needed.
Send it after approval and confirm that it is sent.
"""

@mcp.tool(description=propose_meeting_description)
def propose_meeting(name: str, target_name: str, email: str, my_availability: str) -> str:
    email = f"Hey {target_name}!\n\n" \
        "Would love to meet you soon! Here are my available times over the next week:\n\n" \
        f"{my_availability}\n\n" \
        "Best regards,\n" \
        f"{name}"

    return email



respond_to_proposal_description = """When the user receives emails about scheduling or availability:

Scenario 1: If someone shares their availability
- Automatically find matching free time in your calendar
- Replies confirming the best time
- Adds the meeting to your calendar and send the invite to the person as well

Scenario 2: If someone asks for your availability
- Checks your calendar for free slots
- Replies with your available times
- Waits for confirmation before scheduling 
"""

@mcp.tool(description=respond_to_proposal_description)
def respond_to_proposal():
    return


@dataclass
class TimeInterval:
    start: datetime
    end: datetime
    
    def overlaps(self, other: 'TimeInterval') -> bool:
        return (self.start < other.end) and (other.start < self.end)
    
    def intersection(self, other: 'TimeInterval') -> 'TimeInterval':
        if not self.overlaps(other):
            return None
        start = max(self.start, other.start)
        end = min(self.end, other.end)
        return TimeInterval(start=start, end=end)


def find_availability_intersection(
    slots1: List[TimeInterval],
    slots2: List[TimeInterval]
) -> List[TimeInterval]:
    """Find all overlapping time intervals between two lists of time slots."""
    result = []
    for slot1 in slots1:
        for slot2 in slots2:
            if slot1.overlaps(slot2):
                intersection = slot1.intersection(slot2)
                if intersection:
                    result.append(intersection)
    return result


find_common_availability_description = """
Find overlapping available times between two people.
Should be used when the user wants to find common available times between two people.

Args:
    my_availability: List of {'start': datetime, 'end': datetime}
    friend_availability: List of {'start': datetime, 'end': datetime}
    
Returns:
    List of overlapping time intervals as dicts with 'start' and 'end' ISO format strings
"""


@mcp.tool(description=find_common_availability_description)
def find_common_availability(
    my_availability: List[dict],
    friend_availability: List[dict]
) -> List[dict]:
    # Convert ISO format strings to datetime objects
    def parse_availability(avail_list):
        result = []
        for slot in avail_list:
            start = datetime.fromisoformat(slot['start'])
            end = datetime.fromisoformat(slot['end'])
            result.append(TimeInterval(start=start, end=end))
        return result
    
    my_slots = parse_availability(my_availability)
    friend_slots = parse_availability(friend_availability)
    
    # Find intersections
    common = find_availability_intersection(my_slots, friend_slots)
    
    # Convert back to dict for JSON serialization
    return [{'start': slot.start.isoformat(), 'end': slot.end.isoformat()} 
            for slot in common]

def main():
    port = int(os.environ.get("PORT", 8000))
    host = "0.0.0.0"
    
    print(f"Starting Scheduling server on {host}:{port}")
    
    mcp.run(
        transport="http",
        host=host,
        port=port
    )


if __name__ == "__main__":
    main()
