import json
import os
import time
from dataclasses import asdict
from time import sleep

import requests
import waiting
from pyyoutube import Client

from test.config import Config
from utils.common import root_dir
from utils.db import GUser, get_db_session, YtAutomatedPlaylist, load_yt_automated_playbooks
from utils.jf import get_user_session


def create_db_container(docker_client):
    old_container = next((c for c in docker_client.containers.list(all=True) if c.name == Config.PocketBase.container_name), None)
    if old_container:
        old_container.remove(force=True)
    sleep(1)
    db_container = docker_client.containers.run(Config.PocketBase.image,
                                                name=Config.PocketBase.container_name,
                                                detach=True,
                                                ports=Config.PocketBase.port_mapping)

    def predicate():
        requests.get(Config.PocketBase.url + "/_").raise_for_status()
        return True

    sleep(1)
    waiting.wait(predicate,
                 expected_exceptions=requests.exceptions.ConnectionError,
                 timeout_seconds=20)
    sleep(1)
    code, out = db_container.exec_run(
        f'/bin/pocketbase --dir /exia/pocketbase --hooksDir /exia/pocketbase_hooks --publicDir /exia/pocketbase_public superuser upsert {Config.PocketBase.username} {Config.PocketBase.password}')
    assert code == 0
    print(out.decode())
    return db_container


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

__jf_url__= os.getenv('JELLYFIN_LOCAL_URL')

def get_test_user_session():
    return get_user_session(Config.TestUser.jf_username, Config.TestUser.jf_pw)

def remove_items_from_jf_playlist(pl_id, items):
    if not isinstance(items, str):
        items = ",".join(items)
    user_session = get_test_user_session()
    resp = user_session.delete(f"{__jf_url__}/Playlists/{pl_id}/Items", params={"entryIds": items})
    return resp.status_code == 204
