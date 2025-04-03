import json
import os
import re
import threading
import unittest
from threading import Event

import yt_dlp
from pyyoutube import Client
from slack_sdk.socket_mode.request import SocketModeRequest

import sync
from sync import parse_yt_id, sync_all_playlists, sub_videos_with_songs, sync_playlist, resolve_video_substitution, SLACK_CHANNEL_DEFAULT
from utils import slack
from utils.common import first
from utils.db import load_playlist_configs, load_media_mappings, load_settings, PlaylistConfigResp, load_local_media, load_guser_by_id, load_yt_automated_playbooks
from utils.jf import load_jf_playlist, find_user_by_name, load_all_items, load_item_by_id, save_item, \
    add_media_ids_to_playlist
from utils.logs import create_logger
from utils.web import run_auth_server
from utils.ytm import load_flat_playlist, createYtMusic

logger = create_logger("main")


class MyTestCase(unittest.TestCase):
    def test_replace_1_song(self):
        sync.SLACK_CHANNEL_DEFAULT = '#test'
        resolve_video_substitution(['23g5HBOg3Ic'], 'UFZPMKLKC')


if __name__ == '__main__':
    unittest.main()
