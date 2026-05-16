import json
import os
import time
from dataclasses import asdict

import requests
from pyyoutube import Client
from requests.adapters import HTTPAdapter
from urllib3 import Retry

from test.config import Config
from utils.common import root_dir
from utils.db import GUser, get_db_session, YtAutomatedPlaylist, load_yt_automated_playbooks
from utils.jf import get_user_session, load_all_playlists


def populate_db():
    truncate(GUser)
    insert(GUser(id=None,
                 yt_user_id=Config.TestUser.google_user,
                 yt_username='TestUser',
                 slack_user=Config.TestUser.slack_id,
                 access_token=Config.google_token.access_token,
                 refresh_token=Config.google_token.refresh_token,
                 access_token_expires=int(time.time() + 1000),
                 refresh_token_expires=int(time.time() + 1000)
                 ))


def insert(obj):
    url = f"{Config.PocketBase.url}/api/collections/{obj.col_name}/records"
    resp = get_db_session().post(url, json=asdict(obj))
    resp.raise_for_status()


def truncate(clazz):
    resp = get_db_session().delete(f"{Config.PocketBase.url}/api/collections/{clazz.col_name}/truncate")
    resp.raise_for_status()


def check_yt_token():
    refresh = True
    try:
        response = requests.get(f'https://www.googleapis.com/oauth2/v3/tokeninfo?access_token={Config.google_token.access_token}')
        if response.status_code == 200:
            if int(response.json()['expires_in']) > 60:
                refresh = False
    except:
        pass

    if refresh:
        refresh_access_token()


def refresh_access_token():
    ytc = Client(client_id=os.getenv('GOOGLE_APP_CLIENT_ID'), client_secret=os.getenv('GOOGLE_APP_CLIENT_SECRET'))
    token_upd = ytc.refresh_access_token(Config.google_token.refresh_token)
    Config.google_token.access_token = token_upd.access_token
    with open(root_dir() / 'test/token.json', 'w') as f:
        json.dump(asdict(Config.google_token), f, indent=2)


def is_song(track):
    return track['videoType'] == 'MUSIC_VIDEO_TYPE_ATV'


def create_automated_playlist_cfg(vsd_replace_in_src=False, vsd_replace_during_copy=False, enabled=True, copy=True, truncate_col=True):
    if truncate_col:
        truncate(YtAutomatedPlaylist)
        assert len(load_yt_automated_playbooks()) == 0
    pl = YtAutomatedPlaylist(yt_pl_id=Config.Playlists.yt_src_id,
                             yt_user=Config.TestUser.google_user,
                             enabled=enabled,
                             vsd_replace_in_src=vsd_replace_in_src,
                             vsd_replace_during_copy=vsd_replace_during_copy,
                             copy=copy,
                             copy_dst=Config.Playlists.yt_dst_id,
                             comment="test copying from test_1 to test_2")
    insert(pl)


__jf_url__ = os.getenv('JELLYFIN_LOCAL_URL')


def get_test_user_session():
    return get_user_session(Config.TestUser.jf_username, Config.TestUser.jf_pw)


def remove_items_from_jf_playlist(pl_id, items):
    if not isinstance(items, str):
        items = ",".join(items)
    user_session = get_test_user_session()
    resp = user_session.delete(f"{__jf_url__}/Playlists/{pl_id}/Items", params={"entryIds": items})
    return resp.status_code == 204


def setup_jf_library():
    user_session = get_test_user_session()
    lib_name = "music"
    try:
        user_session.delete(f"{__jf_url__}/Library/VirtualFolders", params={"name": lib_name})
    except:
        pass
    resp = user_session.post(f"{__jf_url__}/Library/VirtualFolders",
                             params={
                                 "name": lib_name,
                                 "collectionType": "music",
                                 "paths": ["/tmp"],
                                 "refreshLibrary": True
                             })
    resp.raise_for_status()

def requests_retry_session(
    retries=3,
    backoff_factor=0.3,
    status_forcelist=(500, 502, 504),
    session=None,
):
    session = session or requests.Session()
    # Define retry strategy
    retry = Retry(
        total=retries, # Total attempts including the first one
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor, # Delay between retries
        status_forcelist=status_forcelist, # HTTP status codes to retry on
    )
    # Mount the adapter to both http and https protocols
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def find_jf_playlist_by_name(name):
    playlists = load_all_playlists()
    for pl in playlists:
        if pl['Name'] == name:
            return pl