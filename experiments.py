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
        resolve_video_substitution(['vEN3mQ0ql30', 'pIf2zL6aCig', 'YFwhijwNShw'], 'UFZPMKLKC')

    def test_run_video_scan(self):
        sub_videos_with_songs()

    def test_remove_all_vids_from_pl(self):
        pl_id = 'PL8xOIxSY5muDGvaFgcV71sADRgxOZtOG7'
        guser_id = os.getenv('GOOGLE_USER_ID')
        usr = load_guser_by_id(guser_id)
        ytc = createYtMusic(usr.access_token, usr.refresh_token)
        playlist = ytc.get_playlist(pl_id, limit=None)
        tracks = playlist['tracks']
        videos = [t for t in tracks if t['videoType'] != 'MUSIC_VIDEO_TYPE_ATV']
        print(f"Removing {len(videos)} videos")
        print('\n'.join([f"{v['title']}" for v in videos]))
        if videos:
            ytc.remove_playlist_items(pl_id, videos)

if __name__ == '__main__':
    unittest.main()
