#!/usr/bin/env python3
"""
Input validation for GM tools: the two checks that are used.
"""

import re


class Validators:
    """Input validation for the GM system."""

    @staticmethod
    def validate_name(name: str) -> tuple[bool, str | None]:
        """
        Validate name/identifier
        Allows: alphanumeric, spaces, hyphens, apostrophes
        Returns: (is_valid, error_message)
        """
        if not name or not name.strip():
            return False, "Name cannot be empty"

        # Check length
        if len(name) > 100:
            return False, "Name too long (max 100 characters)"

        # Check characters
        pattern = r"^[a-zA-Z0-9\s\-']+$"
        if not re.match(pattern, name):
            return False, "Invalid name. Use only letters, numbers, spaces, hyphens, and apostrophes"

        return True, None

    @staticmethod
    def validate_time_of_day(time: str) -> tuple[bool, str | None]:
        """
        Validate a time-of-day word (the same words as time_manager.TIMES_OF_DAY)
        Returns: (is_valid, error_message)
        """
        valid_times = [
            'small hours', 'dawn', 'morning', 'noon',
            'afternoon', 'evening', 'dusk', 'night', 'midnight'
        ]

        time_lower = time.lower().strip()
        if time_lower not in valid_times:
            return False, f"Invalid time. Valid times: {', '.join(valid_times)}"

        return True, None
