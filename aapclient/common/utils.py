# Copyright (c) 2025 Chris Edillon
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Utility functions for AAP client"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence


class CommandError(Exception):
    """Exception raised by CLI commands"""
    pass


def get_dict_properties(data: Dict[str, Any], columns: Sequence[str]) -> List[Any]:
    """Extract values from dictionary based on column list, formatting name fields"""
    result = []
    for col in columns:
        value = data.get(col, '')
        # Format any field containing 'name' in its key (name, project_name, etc.)
        if 'name' in col and col != 'username':  # Don't format username fields
            value = format_name(value)
        result.append(value)
    return result


def find_resource(resources: Dict[str, Any], name_or_id: str) -> Dict[str, Any]:
    """Find a resource by name or ID from a list response"""
    results = resources.get('results', [])

    # Try to find by ID first
    try:
        resource_id = int(name_or_id)
        for resource in results:
            if resource.get('id') == resource_id:
                return resource
    except ValueError:
        pass

    # Try to find by name
    matches = [r for r in results if r.get('name') == name_or_id]
    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        raise CommandError(f"Multiple resources found with name '{name_or_id}'")

    raise CommandError(f"Resource '{name_or_id}' not found")


def format_datetime(dt_string: Optional[str]) -> str:
    """Format a datetime string for display"""
    if not dt_string:
        return ''

    try:
        # Parse ISO format datetime (e.g., "2025-07-01T14:47:53.988589Z")
        if dt_string.endswith('Z'):
            dt = datetime.fromisoformat(dt_string[:-1])
        else:
            dt = datetime.fromisoformat(dt_string)

        # Format for display (removing microseconds for readability)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        return dt_string


def format_duration(start_time: Optional[str], end_time: Optional[str]) -> str:
    """Calculate and format duration between start and end times"""
    if not start_time or not end_time:
        return ''

    try:
        # Parse the datetime strings
        if start_time.endswith('Z'):
            start_dt = datetime.fromisoformat(start_time[:-1])
        else:
            start_dt = datetime.fromisoformat(start_time)

        if end_time.endswith('Z'):
            end_dt = datetime.fromisoformat(end_time[:-1])
        else:
            end_dt = datetime.fromisoformat(end_time)

        # Calculate duration
        duration = end_dt - start_dt
        total_seconds = int(duration.total_seconds())

        # Format as "1h 2m 5s" style, omitting zero values
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        parts = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if seconds > 0 or not parts:  # Always show seconds if nothing else, or if seconds > 0
            parts.append(f"{seconds}s")

        return " ".join(parts)
    except (ValueError, TypeError):
        return ''


def format_name(name: Any) -> str:
    """Format a resource name, wrapping numeric names in double quotes"""
    if name is None:
        return ''

    name_str = str(name)

    # Check if the name is numeric (integer or float)
    try:
        # Try parsing as int first, then float
        int(name_str)
        return f'"{name_str}"'  # Wrap numeric names in quotes
    except ValueError:
        try:
            float(name_str)
            return f'"{name_str}"'  # Wrap numeric names in quotes
        except ValueError:
            return name_str  # Return as-is for non-numeric names
