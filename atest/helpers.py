import json
import os
import time
from dataclasses import asdict
from time import sleep

import requests
import waiting
from pyyoutube import Client

from atest.config import Config
from utils.common import root_dir
from utils.db import GUser, get_db_session


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
    waiting.wait(predicate, expected_exceptions=requests.exceptions.ConnectionError, timeout_seconds=10)
    sleep(1)
    code, out = db_container.exec_run(
        f'/bin/pocketbase --dir /exia/pocketbase --hooksDir /exia/pocketbase_hooks --publicDir /exia/pocketbase_public superuser upsert {Config.PocketBase.username} {Config.PocketBase.password}')
    assert code == 0
    print(out.decode())
    return db_container


def populate_db():
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
    with open(root_dir() / 'atest/token.json', 'w') as f:
        json.dump(asdict(Config.google_token), f, indent=2)
