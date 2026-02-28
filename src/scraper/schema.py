"""
Module: src/scraper/schema.py
Purpose: Define the unified course schema and normalization utilities.
"""

import re

COURSE_FIELDS = [
    "course_code",
    "title",
    "instructor",
    "meeting_times",
    "prerequisites",
    "department",
    "description",
    "source",
]


def empty_course():
    """Create a new course dictionary with all fields initialized to empty strings."""
    return {field: "" for field in COURSE_FIELDS}


def normalize_course_code(code: str) -> str:
    """Normalize course codes to 'DEPT NNNN' format.

    Handles variations like 'CSCI0320', 'CSCI 0320', 'CSCI  0320'.
    """
    code = code.strip()
    m = re.match(r"([A-Z]{2,6})\s*(\d{4}[A-Z]?)", code)
    if m:
        return f"{m.group(1)} {m.group(2)}"
    return code
