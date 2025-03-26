import json
import os
import re
import threading
import unittest
from threading import Event

import yt_dlp
from pyyoutube import Client
from slack_sdk.socket_mode.request import SocketModeRequest

from sync import parse_yt_id, sync_all_playlists, sub_videos_with_songs, sync_playlist
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
    def test_something(self):
        create_logger("test")
        URL = 'https://music.youtube.com/playlist?list=PL8xOIxSY5muDrDAEvl-uwE9SqbLl1pnnt'
        ydl_opts = {'extract_flat': True,
                    'lazy_playlist': True}

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(URL, download=False, extra_info={'extract_flat': True})
            # ℹ️ ydl.sanitize_info makes the info json-serializable
            print(json.dumps(ydl.sanitize_info(info)))

    def test_load_config(self):
        configs = load_playlist_configs()
        pass

    def test_load_media_mappings(self):
        mappings = load_media_mappings()
        pass

    def test_load_settings(self):
        settings = load_settings()
        print(settings)

    def test_sync_playlists(self):

        sync_all_playlists()

    def test_update_yt_id(self):
        mappings = load_media_mappings()
        jf_items = load_all_items("Audio", "Path,ProviderIds")
        settings = load_settings()
        user = find_user_by_name(settings.jf_user_name)
        for m in mappings:
            jf_path = re.sub(settings.pf2jf_path_conv_search, settings.pf2jf_path_conv_replace, m.local_path)
            jf_item = next((i for i in jf_items if i['Path'] == jf_path), None)
            if jf_item:
                jf_id = jf_item['Id']
                jf_name = jf_item['Name']
                yt_provider_id = jf_item['ProviderIds'].get('YT')
                if yt_provider_id is None:
                    jf_item_full = load_item_by_id(jf_id, user.id)
                    jf_item_full['ProviderIds']['YT'] = m.yt_id
                    assert save_item(jf_item_full)
                    logger.info(f"Media '{jf_name}'({jf_id}) got updated with YT id {m.yt_id}")
                else:
                    logger.info(f"Media '{jf_name}'({jf_id}) already has YT id {yt_provider_id}")
            else:
                logger.warn(f"Cannot find JellyFin Item for path [{jf_path}]")
        pass

    def test_sync_1_playlist(self):
        pl_config = PlaylistConfigResp('', 'aa25b691a51fdc12c6c66d7cdeb58056', 'AlisaYTM',
                                       'PLmK_pBmX9bLEbzPI7OCeILf9fg4k1-koA', 'Alisa_likes')
        jf_items = load_all_items("Audio", "ProviderIds")
        ytm2items = {itm['ProviderIds']['YT']: itm for itm in jf_items if 'YT' in itm['ProviderIds']}
        settings = load_settings()
        user = find_user_by_name(settings.jf_user_name)
        yt_playlist_songs = load_flat_playlist(pl_config.ytm_pl_id)
        jf_playlist_songs = load_jf_playlist(pl_config.jf_pl_id, user.id, "ProviderIds")
        jf_playlist_yt_ids = {e['ProviderIds']['YT'] for e in jf_playlist_songs['Items']}
        already_in_library = []
        for yt_song in yt_playlist_songs['entries']:
            yt_id = yt_song['id']
            if yt_id in jf_playlist_yt_ids:
                # This song is already in the JF playlist
                continue
            jf_item = ytm2items.get(yt_id)
            if jf_item:
                already_in_library.append(jf_item['Id'])
                logger.info(
                    f"Queueing media '{jf_item['Name']}'[{yt_song['url']}] into JF playlist '{pl_config.jf_pl_id}'")
            else:
                logger.warning(
                    f"Cannot find media '{yt_song['channel']}/{yt_song['title']}'[{yt_song['url']}] in local library.")
        added_n = add_media_ids_to_playlist(pl_config.jf_pl_id, already_in_library, user_id=user.id)

        log_level_func = logger.info if added_n == len(already_in_library) else logger.warning
        log_level_func(
            f"Added {added_n} out of {len(already_in_library)} possible medias into the playlist {pl_config.jf_pl_id}")

    def test_ytm_load_playlist(self):
        pl_id = 'PL8xOIxSY5muBpfssqpnGSAfGIeJlR9Za0'
        pl = load_flat_playlist(pl_id)
        with open('tmp/ytm_playlist.json', 'w') as f:
            json.dump(pl, f, indent=2)
        pass

    def test_jf_load_playlist(self):
        pl_id = 'bdf3964ebdcfbbd1e94eb3937dadc486'
        user_id = '85e1d3cd5c8b49de9c225d5f8d39e79e'
        pl = load_jf_playlist(pl_id, user_id)
        with open('tmp/jf_playlist.json', 'w') as f:
            json.dump(pl, f, indent=2)
        pass

    def test_jf_find_user(self):
        user_name = 'abc'
        user = find_user_by_name(user_name)
        with open('tmp/jf_user.json', 'w') as f:
            json.dump(user.raw, f, indent=2)
        pass

    def test_get_yt_pl_title(self):
        URL = 'https://music.youtube.com/playlist?list=PL8xOIxSY5muDrDAEvl-uwE9SqbLl1pnnt'
        ydl_opts = {'extract_flat': True}

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(URL, download=False, process=False)
            # ℹ️ ydl.sanitize_info makes the info json-serializable
            print(json.dumps(ydl.sanitize_info(info)))

    def test_date_field(self):
        media = load_local_media()
        pass

    def test_slack_message(self):
        slack.send_message("Just a test message", "#test")

    def test_slack_message_formatted(self):
        slack.send_message("Just a *test* message with a <http://google.com|link>", "#test")

    def test_slack_interactive(self):
        slack.send_message("Just a test message", "#test")
        threading.Event().wait()

    def test_slack_message_blocks(self):
        layout = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "New request",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": "*Type:*\nPaid Time Off"
                    },
                    {
                        "type": "mrkdwn",
                        "text": "*Created by:*\n<example.com|Fred Enriquez>"
                    }
                ]
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": "*When:*\nAug 10 - Aug 13"
                    }
                ]
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "emoji": True,
                            "text": "Approve"
                        },
                        "style": "primary",
                        "value": json.dumps({
                            "type": "media_metadata_mismatch",
                            "action": "confirm",
                            "yt_id": 'aaaaaaa',
                            "jf_id": 'bbbbbbb'
                        })
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "emoji": True,
                            "text": "Reject"
                        },
                        "style": "danger",
                        "value": json.dumps({
                            "type": "media_metadata_mismatch",
                            "action": "deny",
                            "yt_id": 'aaaaaaaaa',
                            "jf_id": 'bbbbbbbbb'
                        })
                    }
                ]
            }
        ]
        parse_yt_id('hgjhgfjgh')
        slack.send_message("Just a *test* message with a <http://google.com|link>", "#test", blocks=layout)
        threading.Event().wait()

    def test_video_song_sub(self):
        sub_videos_with_songs()

    def test_YTMusic_oauth(self):
        at = 'ya29.a0AeXRPp49JdEeYAW58-wPejnAIikVdDKLThbGkm0GH1wPzIVUc3skzCgmdLpgaT1v5UpSW9lvdMKTkZEOnLSOleKsi3iLMkCQiXxC-zTf_mVYV2imLLsY6jj24YybAKlO1_rKKPaGv9ktCykCO1c7Y8WfT9Fuhp0p_jkGK9_NaCgYKARASARESFQHGX2MiOr5TEIRPkT5FE43GYa6lPg0175'
        rt = '1//05p42oaAOJSA-CgYIARAAGAUSNwF-L9IreNBjDWRH5fKav4f6gijWSwwzMQBoQHXiLuSbn8-aYddyKd9fEJFO3jexEpT4T2R9Phw'

        ytmusic = createYtMusic(at, rt)
        song = ytmusic.get_song('bY3vXr7fm8k')
        pass

    def test_slack_bot(self):
        slack.__setup_slack_callback__()
        Event().wait()

    def test_slack_socket_mode(self):
        ytc = Client(client_id=os.getenv('GOOGLE_APP_CLIENT_ID'), client_secret=os.getenv('GOOGLE_APP_CLIENT_SECRET'))

        def on_shortcut(req: SocketModeRequest):
            guser_id = os.getenv('GOOGLE_USER_ID')
            usr = load_guser_by_id(guser_id)
            playbooks = [pl for pl in load_yt_automated_playbooks() if pl.yt_pl_id == usr.yt_user_id]
            if playbooks:
                if usr.is_refresh_token_valid():
                    if not usr.is_access_token_valid():
                        # Replace with a token refresh
                        return
                playlists_list = ytc.playlists.list(playlist_id=[pl.yt_pl_id for pl in playbooks])

            authorize_url, app_name = ytc.get_authorize_url(scope=['https://www.googleapis.com/auth/youtube', 'https://www.googleapis.com/auth/userinfo.profile'],
                                                            redirect_uri='https://localhost:1234/abc',
                                                            state='abc',
                                                            prompt="consent")

            slack.send_ephemeral(authorize_url, req.payload['user']['id'], req.payload['user']['id'])
            pass

        slack.add_slack_shortcut_handler('vsd-init-scan', on_shortcut)
        slack.__setup_slack_callback__()
        run_auth_server(ytc)

    def test_sync_playlist(self):
        pl = first(pl for pl in load_playlist_configs() if pl.jf_pl_name=='roadtrip')
        sync_playlist(pl)
        pass

if __name__ == '__main__':
    unittest.main()
