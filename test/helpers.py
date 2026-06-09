import io
import json
import os
import tarfile
import time
from dataclasses import asdict

import requests
from docker.models.containers import Container
from pyyoutube import Client
from requests.adapters import HTTPAdapter
from urllib3 import Retry

from test.config import Config
from utils.common import root_dir
from utils.db import GUser, get_db_session, YtAutomatedPlaylist, load_yt_automated_playbooks, Settings, load_settings
from utils.jf import get_user_session, load_all_playlists, remove_item, load_all_items, reload_library


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
    return resp.json()['id']


def delete(obj):
    url = f"{Config.PocketBase.url}/api/collections/{obj.col_name}/records/{obj.id}"
    resp = get_db_session().delete(url)
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
                                 "paths": [Config.JellyFin.music_lib_dir],
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

def copy_files_into_docker_container(container:Container, dst_path, *src_paths):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w:gz') as tar:  # 'w:gz' for gzip, 'w' for uncompressed
        for src in src_paths:
            tar.add(src, arcname=os.path.basename(src))
    container.put_archive(dst_path, buf.getvalue())

def copy_single_file_into_docker_container(container:Container, dst_path, src_path):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w:gz') as tar:  # 'w:gz' for gzip, 'w' for uncompressed
        tar.add(src_path, arcname=os.path.basename(dst_path))
    container.put_archive(os.path.dirname(dst_path), buf.getvalue())

def remove_jf_playlist(pl_id):
    return remove_item(pl_id)

def jf_has_song_with_yt_id(yt_id):
    itms = load_all_items("Audio", "Path")
    return next((s for s in itms if yt_id in s['Path']), None) is not None


def retry_on_exception(func, retries=7, delay=1, backoff=2):
    for i in range(retries - 1):
        try:
            return func()
        except:
            print(f"Attempt {i + 1}/{retries} failed, retrying in {delay} seconds...")
            time.sleep(delay)
            delay *= backoff
    return func()


def reload_lib_until_song_found_n_times(yt_id, n=1, max_retries=5):
    def predicate():
        return n == sum(1 for s in load_all_items("Audio", "Path") if yt_id in s['Path'])

    sleep_time = 1
    sleep_time_multiplier = 2
    for i in range(max_retries):
        try:
            if predicate():
                return True
            print(f"Retrying reload library... attempt {i + 1}/{max_retries}")
            reload_library()
        except:
            pass
        time.sleep(sleep_time)
        sleep_time = sleep_time * sleep_time_multiplier
    return False


def save_settings(settings: Settings):
    url = f"{Config.PocketBase.url}/api/collections/yt_sync_settings/records"
    response = get_db_session().get(url)
    key2id = {entry['key']: entry['id'] for entry in response.json()['items']}
    for key, entry_id in key2id.items():
        val = getattr(settings, key)
        resp = get_db_session().patch(f"{url}/{entry_id}", json={"val": val})
        resp.raise_for_status()
    load_settings.cache_clear()

def get_yt_id(jf_item):
    try:
        return jf_item['ProviderIds']['YT']
    except:
        return None