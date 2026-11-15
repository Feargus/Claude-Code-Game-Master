#!/usr/bin/env python3
"""
Input validation for GM tools: the two checks that are used.
"""


class Validators:
    """Input validation for the GM system."""

    @staticmethod
    def validate_name(name: str) -> tuple[bool, str | None]:
        """A name for a person or place: letters of any alphabet (Kostić, Inês),
        digits, spaces, hyphens, apostrophes and full stops (Dr. Strand).
        No colon: it separates the kind from the name in an id (npc:<name>).
        Returns: (is_valid, error_message)
        """
        if not name or not name.strip():
            return False, "Name cannot be empty"
        if len(name) > 100:
            return False, "Name too long (max 100 characters)"
        bad = sorted({c for c in name if not (c.isalnum() or c.isspace() or c in "-'’.")})
        if bad:
            return False, (f"Invalid name '{name}': it can't contain {' '.join(bad)}. Use letters, "
                           "numbers, spaces, hyphens, apostrophes and full stops.")
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
