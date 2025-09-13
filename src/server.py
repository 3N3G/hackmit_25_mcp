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

propose_meeting_description = """Returns the email to propose a meeting to another user. 
Should be used when the user wants to schedule or propose a meeting to another user

Args:
    name: The name of the user
    target_name: The name of the target user
    email: The email of the target user
    my_availability: The availability of the user

Returns:
    The email to propose a meeting to another user
"""

@mcp.tool(description=propose_meeting_description)
def propose_meeting(name: str, target_name: str, email: str, my_availability: str) -> str:
    email = f"Hey {target_name}!\n\n" \
        "Would love to meet you soon! Here are my available times over the next week:\n\n" \
        f"{my_availability}\n\n" \
        "Best regards,\n" \
        f"{name}"

    return email


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
