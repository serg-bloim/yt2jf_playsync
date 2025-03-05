from sync import update_yt_ids_in_db, sync_all_playlists, update_pl_cfg_in_db
from utils.logs import create_logger

logger = create_logger("main")


def main():
    logger.info("Starting the sync")
    update_pl_cfg_in_db()
    update_yt_ids_in_db()
    sync_all_playlists()

if __name__ == "__main__":
    main()