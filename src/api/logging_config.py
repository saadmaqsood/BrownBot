"""
Module: src/api/logging_config.py
Purpose: Query logging configuration.
"""

import logging
import os

LOG_DIR = os.getenv("LOG_DIR", "logs")
LOG_FILE = os.path.join(LOG_DIR, "queries.log")

os.makedirs(LOG_DIR, exist_ok=True)

query_logger = logging.getLogger("brownbot.queries")
query_logger.setLevel(logging.INFO)

handler = logging.FileHandler(LOG_FILE)
handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
query_logger.addHandler(handler)
