import logging
import sys

# Set up logging to stdout
logging.basicConfig(
    level=logging.DEBUG,  # Set logging level (DEBUG, INFO, etc.)
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout  # Logs to stdout
)


def logs_init():
    pass


def create_logger(name):
    return logging.getLogger(name)
