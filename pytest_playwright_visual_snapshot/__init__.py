import logging
import os

log = logging.getLogger(__name__)

def main():
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "WARNING"))
    log.info("Hello, Logs!")
