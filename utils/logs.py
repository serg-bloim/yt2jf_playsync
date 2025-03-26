import logging
import os
import sys
from logging import INFO

# Set up logging to stdout
logging.basicConfig(
    level=logging.getLevelNamesMapping().get(os.getenv('LOG_LEVEL')) or INFO,  # Set logging level (DEBUG, INFO, etc.)
    format='%(asctime)s - %(levelname)s [%(name)s] - %(message)s',
    stream=sys.stdout  # Logs to stdout
)


def logs_init():
    pass


def create_logger(name):
    return logging.getLogger(name)
