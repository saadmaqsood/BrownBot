#!/usr/bin/env python3
"""
Module: scripts/run_scrape.py
Purpose: ETL entry point — scrape CAB + Bulletin, merge, save to data/courses.json.
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.scraper.bulletin import fetch_courses_bulletin
from src.scraper.courses import fetch_courses_cab
from src.scraper.merged import merge_courses, save_courses_json


def main():
    parser = argparse.ArgumentParser(description="Scrape and merge Brown course data")
    parser.add_argument("--bulletin-only", action="store_true", help="Only scrape Bulletin")
    parser.add_argument("--cab-only", action="store_true", help="Only scrape CAB")
    parser.add_argument("-o", "--output", default="data/courses.json", help="Output file path")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    if args.bulletin_only:
        courses = fetch_courses_bulletin()
        for c in courses:
            c["source"] = "Bulletin"
    elif args.cab_only:
        courses = fetch_courses_cab()
    else:
        cab = fetch_courses_cab()
        bulletin = fetch_courses_bulletin()
        courses = merge_courses(cab, bulletin)

    save_courses_json(courses, args.output)
    print(f"Done. {len(courses)} courses saved to {args.output}")


if __name__ == "__main__":
    main()
