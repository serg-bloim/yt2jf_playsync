from typing import Iterable

import docker
import pytest
from docker import DockerClient
from docker.models.containers import Container
from ytmusicapi import YTMusic

import atest
import sync
from atest.config import Config
from atest.helpers import create_db_container, populate_db, check_yt_token, is_song, create_automated_playlist_cfg, insert, truncate_collection
from sync import sub_videos_with_songs
from utils import db
from utils.db import load_yt_media_metadata, YtMediaMetadata
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
    truncate_collection(YtMediaMetadata)
    mm = YtMediaMetadata(id=None, yt_id=src_video1_id, title='Test Title', artist='Test artist', category='video', album_name='Test album', duration=123, alt_id='BUWiEPJCbjs', ignore=False)
    insert(mm)
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
    create_automated_playlist_cfg(truncate=True)
    src_ids, src_id, dst_id = yt_playlists
    sub_videos_with_songs()
    ytm = createYtMusic(Config.google_token.access_token, Config.google_token.refresh_token)
    pl_src = ytm.get_playlist(src_id)
    pl_dst = ytm.get_playlist(dst_id)
    assert set(src_ids) == set(t['videoId'] for t in pl_src['tracks'])
    assert set(src_ids) == set(t['videoId'] for t in pl_dst['tracks'])
    assert set(src_ids).issubset(set(mm.yt_id for mm in load_yt_media_metadata()))


def test_yt_copy_to_playlist_songs_and_converted_videos(yt_playlists):
    create_automated_playlist_cfg(vsd_replace_during_copy=True, truncate=True)
    src_ids, src_id, dst_id = yt_playlists
    ytm = createYtMusic(Config.google_token.access_token, Config.google_token.refresh_token)
    pl_src_original = ytm.get_playlist(src_id)
    songs = {t['videoId'] for t in pl_src_original['tracks'] if is_song(t)}
    src_videos = {t['videoId'] for t in pl_src_original['tracks'] if not is_song(t)}
    sub_videos_with_songs()
    pl_src = ytm.get_playlist(src_id)
    pl_dst = ytm.get_playlist(dst_id)
    # Src playlist got unchanged
    assert [t['videoId'] for t in pl_src['tracks']] == [t['videoId'] for t in pl_src_original['tracks']]
    # Dst playlist got only songs and converted videos from Src
    converted_vids = {mm.alt_id for mm in load_yt_media_metadata() if mm.yt_id in src_videos and mm.alt_id}
    expected = songs.union(converted_vids)
    assert expected == {t['videoId'] for t in pl_dst['tracks']}


def test_yt_copy_to_playlist_replace_in_src(yt_playlists):
    create_automated_playlist_cfg(vsd_replace_during_copy=True, vsd_replace_in_src=True, truncate=True)
    src_ids, src_id, dst_id = yt_playlists
    ytm = createYtMusic(Config.google_token.access_token, Config.google_token.refresh_token)
    pl_src_original = ytm.get_playlist(src_id)
    songs = {t['videoId'] for t in pl_src_original['tracks'] if is_song(t)}
    src_videos = {t['videoId'] for t in pl_src_original['tracks'] if not is_song(t)}
    sub_videos_with_songs()
    pl_src = ytm.get_playlist(src_id)
    pl_dst = ytm.get_playlist(dst_id)
    converted_vids = {mm.yt_id:mm.alt_id for mm in load_yt_media_metadata() if mm.yt_id in src_videos and mm.alt_id}
    # Src playlist got possible videos replaced
    expected_src = songs.union(src_videos).union(converted_vids.values()).difference(converted_vids.keys())
    # Dst playlist got only songs and converted videos from Src
    expected_dst = songs.union(converted_vids.values())
    assert expected_src == {t['videoId'] for t in pl_src['tracks']}
    assert expected_dst == {t['videoId'] for t in pl_dst['tracks']}
