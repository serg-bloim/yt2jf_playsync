import configparser
import time
from datetime import timedelta

import pytimeparse

from sync import update_yt_ids_in_db, sync_all_playlists, update_pl_cfg_in_db
from utils.db import load_settings
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
    docker_v = config['core']['docker_version']
    code_v = config['core']['code_version']
    return f"{docker_v} / {code_v}"


def main():
    logger.info(f"Starting the sync. Version: {read_version()}")
    update_pl_cfg_in_db()
    update_yt_ids_in_db()
    sync_all_playlists()
    wait_period()


if __name__ == "__main__":
    main()
