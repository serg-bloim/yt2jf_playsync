from typing import Iterable

import docker
import pytest
from docker import DockerClient
from docker.models.containers import Container
from ytmusicapi import YTMusic

import atest
import sync
from atest.config import Config
from atest.helpers import create_db_container, populate_db, check_yt_token, insert
from sync import sub_videos_with_songs
from utils import db
from utils.db import YtAutomatedPlaylist, load_yt_automated_playbooks, load_yt_media_metadata
from utils.ytm import createYtMusic

docker_client: DockerClient
db_container: Container

atest.update_envvar()

def yt_plailist_set_items(ytc: YTMusic, pl_id: str, item_ids: Iterable[str]):
    item_ids = set(item_ids)
    src_playlist = ytc.get_playlist(pl_id)
    tracks = src_playlist['tracks']
    tracks_to_remove = [t for t in tracks if t['videoId'] not in item_ids]
    if tracks_to_remove:
        ytc.remove_playlist_items(pl_id, tracks_to_remove)
    existing_ids = {t['videoId'] for t in tracks}
    tracks_to_add = [id for id in item_ids if id not in existing_ids]
    if tracks_to_add:
        ytc.add_playlist_items(pl_id, tracks_to_add)


@pytest.fixture
def yt_playlists():
    print("Prepare YT playlists")
    src_song_id = 'KJATZ3XwvL8'
    src_video1_id = 'yF9MVbVO1IY'
    src_video2_id = 'DrHd3nkCIz4'
    ytc = createYtMusic(Config.google_token.access_token, Config.google_token.refresh_token)
    src_items_to_add = [src_song_id, src_video1_id, src_video2_id]
    pl_src_id = Config.Playlists.yt_src_id
    pl_dst_id = Config.Playlists.yt_dst_id
    yt_plailist_set_items(ytc, pl_src_id, src_items_to_add)
    yt_plailist_set_items(ytc, pl_dst_id, [])
    yield src_items_to_add, pl_src_id, pl_dst_id


def setup_module(module):
    print("module setup")
    global docker_client, db_container
    sync.SLACK_CHANNEL_DEFAULT = "#test"
    sync.SLACK_CHANNEL_INFO = sync.SLACK_CHANNEL_DEFAULT
    sync.SLACK_CHANNEL_MISMATCHED_MEDIA = sync.SLACK_CHANNEL_DEFAULT
    sync.SLACK_CHANNEL_V2S_LOG = sync.SLACK_CHANNEL_DEFAULT
    check_yt_token()
    current_ctx = docker.context.Context.load_context(docker.context.api.get_current_context_name())
    url = current_ctx.endpoints["docker"]["Host"]
    docker_client = docker.DockerClient(base_url=url)
    db_container = create_db_container(docker_client)
    db.create_db_structure()
    populate_db()


def teardown_module(module):
    print("module teardown")
    db_container.remove(force=True)
    docker_client.close()


def test_yt_copy_to_playlist_no_replace(yt_playlists):
    assert len(load_yt_automated_playbooks()) == 0
    pl = YtAutomatedPlaylist(yt_pl_id=Config.Playlists.yt_src_id,
                             yt_user=Config.TestUser.google_user,
                             enabled=True,
                             vsd_replace_in_src=False,
                             vsd_replace_during_copy=False,
                             copy=True,
                             copy_dst=Config.Playlists.yt_dst_id,
                             comment="atest copying from test_1 to test_2")
    src_ids, src_id, dst_id = yt_playlists
    insert(pl)
    sub_videos_with_songs()
    ytm = createYtMusic(Config.google_token.access_token, Config.google_token.refresh_token)
    pl_src = ytm.get_playlist(src_id)
    pl_dst = ytm.get_playlist(dst_id)
    assert set(src_ids) == set(t['videoId'] for t in pl_src['tracks'])
    assert set(src_ids) == set(t['videoId'] for t in pl_dst['tracks'])
    assert set(src_ids).issubset(set(mm.yt_id for mm in load_yt_media_metadata()))

