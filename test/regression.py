from typing import Iterable

import docker
import pytest
from docker import DockerClient
from docker.models.containers import Container
from ytmusicapi import YTMusic

import sync
from sync import sub_videos_with_songs
from test.config import Config
from test.helpers import create_db_container, populate_db, check_yt_token, is_song, create_automated_playlist_cfg, insert, truncate, remove_items_from_jf_playlist
from utils import db
from utils.db import load_yt_media_metadata, YtMediaMetadata, load_playlist_configs, PlaylistConfigResp
from utils.jf import find_user_by_name, load_item_by_id, save_item
from utils.ytm import createYtMusic

docker_client: DockerClient
db_container: Container
express_mode = True

# The tests require a proper google authentication
# If auth token is expired, renew it using this test method
# test.google_oauth.test_login

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
    src_song_id = 'KJATZ3XwvL8'
    src_video1_id = 'yF9MVbVO1IY'
    src_video2_id = 'DrHd3nkCIz4'
    ytc = createYtMusic(Config.google_token.access_token, Config.google_token.refresh_token)
    src_items_to_add = [src_song_id, src_video1_id, src_video2_id]
    pl_src_id = Config.Playlists.yt_src_id
    pl_dst_id = Config.Playlists.yt_dst_id
    yt_plailist_set_items(ytc, pl_src_id, src_items_to_add)
    yt_plailist_set_items(ytc, pl_dst_id, [])
    truncate(YtMediaMetadata)
    mm = YtMediaMetadata(id=None, yt_id=src_video1_id, title='Test Title', artist='Test artist', category='video', album_name='Test album', duration=123, alt_id='BUWiEPJCbjs', ignore=False)
    insert(mm)
    yield src_items_to_add, pl_src_id, pl_dst_id


@pytest.fixture
def jf_playlists():
    print("Prepare JF playlists")
    truncate(PlaylistConfigResp)
    jf_playlist_id = '2bcaa80fe3ff855242c17e32bb634e56'
    pl_cfg = PlaylistConfigResp(id=None,
                                jf_pl_id=jf_playlist_id,
                                jf_pl_name='test1',
                                ytm_pl_id='PL8xOIxSY5muApCYDDmUiKZyKMpdNMt-pM',
                                ytm_pl_name='test_1',
                                jf_user_name='test',
                                sync=True)
    insert(pl_cfg)
    jf_id_recovery_success = '92b50125ec6cb8ae004cf116b1038aff'
    jf_id_recovery_failure = '6ac5a790a7d76a0106f8f02489d154e0'
    yield jf_playlist_id, [jf_id_recovery_success, jf_id_recovery_failure], []


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
    has_db_container_running = 1 == len(docker_client.containers.list(filters={'name': Config.PocketBase.container_name, 'status': 'running'}))
    if not (express_mode and has_db_container_running):
        db_container = create_db_container(docker_client)
        db.create_db_structure()
    populate_db()


def teardown_module(module):
    if not express_mode:
        print("module teardown")
        db_container.remove(force=True)
        docker_client.close()


def test_yt_copy_to_playlist_no_replace(yt_playlists):
    create_automated_playlist_cfg(truncate_col=True)
    src_ids, src_id, dst_id = yt_playlists
    sub_videos_with_songs()
    ytm = createYtMusic(Config.google_token.access_token, Config.google_token.refresh_token)
    pl_src = ytm.get_playlist(src_id)
    pl_dst = ytm.get_playlist(dst_id)
    assert set(src_ids) == set(t['videoId'] for t in pl_src['tracks'])
    assert set(src_ids) == set(t['videoId'] for t in pl_dst['tracks'])
    assert set(src_ids).issubset(set(mm.yt_id for mm in load_yt_media_metadata()))


def test_yt_copy_to_playlist_songs_and_converted_videos(yt_playlists):
    create_automated_playlist_cfg(vsd_replace_during_copy=True, truncate_col=True)
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
    create_automated_playlist_cfg(vsd_replace_during_copy=True, vsd_replace_in_src=True, truncate_col=True)
    src_ids, src_id, dst_id = yt_playlists
    ytm = createYtMusic(Config.google_token.access_token, Config.google_token.refresh_token)
    pl_src_original = ytm.get_playlist(src_id)
    songs = {t['videoId'] for t in pl_src_original['tracks'] if is_song(t)}
    src_videos = {t['videoId'] for t in pl_src_original['tracks'] if not is_song(t)}
    sub_videos_with_songs()
    pl_src = ytm.get_playlist(src_id)
    pl_dst = ytm.get_playlist(dst_id)
    converted_vids = {mm.yt_id: mm.alt_id for mm in load_yt_media_metadata() if mm.yt_id in src_videos and mm.alt_id}
    # Src playlist got possible videos replaced
    expected_src = songs.union(src_videos).union(converted_vids.values()).difference(converted_vids.keys())
    # Dst playlist got only songs and converted videos from Src
    expected_dst = songs.union(converted_vids.values())
    assert expected_src == {t['videoId'] for t in pl_src['tracks']}
    assert expected_dst == {t['videoId'] for t in pl_dst['tracks']}


def test_sync_playlist(yt_playlists, jf_playlists):
    # Prep the media in JF
    test_user = find_user_by_name('test')
    jf_playlist_id, jf_ids_recovery_success, jf_ids_recovery_failure = jf_playlists
    for jf_id in jf_ids_recovery_success + jf_ids_recovery_failure:
        jf_item_full = load_item_by_id(jf_id, test_user.id)
        jf_item_full['ProviderIds'].pop('YT', None)
        assert save_item(jf_item_full)
    playlist_items = jf_ids_recovery_success + jf_ids_recovery_failure
    remove_items_from_jf_playlist(jf_playlist_id, playlist_items)
    # Prep the media in JF

    pl_cfg = load_playlist_configs()[0]
    user = find_user_by_name(pl_cfg.jf_user_name)
    added_into_playlist, not_found = sync.sync_playlist(pl_cfg, user=user)
    assert set(jf_ids_recovery_success) == set(added_into_playlist)
