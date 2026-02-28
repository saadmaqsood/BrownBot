#!/usr/bin/env python3
"""
Module: scripts/run_ingest.py
Purpose: CLI entry point for Qdrant ingestion.
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.rag.ingest import ingest


def main():
    parser = argparse.ArgumentParser(description="Ingest courses into Qdrant")
    parser.add_argument("-f", "--file", default="data/courses.json", help="Input courses JSON")
    parser.add_argument("--batch-size", type=int, default=256, help="Batch size for upserts")
    args = parser.parse_args()

    count = ingest(data_file=args.file, batch_size=args.batch_size)
    print(f"Done. {count} courses ingested into Qdrant.")


if __name__ == "__main__":
    main()
