import configparser
import time
from datetime import timedelta

import pytimeparse

from sync import update_yt_ids_in_db, sync_all_playlists, update_pl_cfg_in_db
from utils.common import get_nested_value
from utils.db import load_settings, create_db_structure
from utils.logs import create_logger

logger = create_logger("main")


def wait_period():
    settings = load_settings()
    wait_time = pytimeparse.parse(settings.wait_time)
    logger.info(f"Waiting for {timedelta(seconds=wait_time)} before next execution")
    time.sleep(wait_time)


def read_version():
    config = configparser.ConfigParser()
    config.read('version.txt')
    docker_v = get_nested_value(config, 'core', 'docker_version') or 'NO_VERSION'
    code_v = get_nested_value(config, 'core', 'code_version') or 'NO_VERSION'
    return f"{docker_v} / {code_v}"


def setup_db_structure():
    create_db_structure()


def main():
    logger.info(f"Version: {read_version()}")
    setup_db_structure()
    logger.info(f"Starting the sync.")
    update_pl_cfg_in_db()
    update_yt_ids_in_db()
    sync_all_playlists()
    wait_period()


if __name__ == "__main__":
    main()
