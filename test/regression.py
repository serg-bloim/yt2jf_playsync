from types import SimpleNamespace

import pytest

from sync import update_pl_cfg_in_db, sync_playlist, process_download_tasks
from test.config import Config
from test.helpers import insert, truncate, find_jf_playlist_by_name, remove_jf_playlist, copy_single_file_into_docker_container, delete, \
    jf_has_song_with_yt_id, reload_lib_until_song_found_n_times
from utils.db import PlaylistConfigResp, load_playlist_configs, load_download_tasks, DownloadTask
from utils.jf import load_jf_playlist, create_playlist, find_user_by_name, add_media_ids_to_playlist, load_all_items, load_item_by_id, save_item, reload_library
from utils.ytm import load_flat_playlist


def test_stage_1_update_pl_cfg_in_db_scenario_1(local_infra, jf_session):
    """Test that playlist configuration is correctly created in the database."""
    # This test would call the function that updates the playlist configuration in the database
    # and then verify that the expected configuration is present in the database.
    # The actual implementation would depend on how the database is structured and how the configuration is stored.
    truncate(PlaylistConfigResp)
    pl_cfg = PlaylistConfigResp(id=None,
                                jf_pl_id=None,
                                jf_pl_name=None,
                                ytm_pl_id='PL8xOIxSY5muApCYDDmUiKZyKMpdNMt-pM',
                                ytm_pl_name='WRONG_NAME',
                                jf_user_name='test',
                                sync=True)
    insert(pl_cfg)
    update_pl_cfg_in_db()
    pl_cfg_upd = load_playlist_configs()[0]
    assert pl_cfg_upd.jf_pl_id is not None, "JF playlist ID should be set in the database"
    assert pl_cfg_upd.jf_pl_name == pl_cfg_upd.ytm_pl_name, "JF playlist name should match the YT playlist name in the database"
    assert pl_cfg_upd.jf_pl_name == 'test_1', "Newly created JF playlist name should match the actual YT playlist name"


def test_stage_1_update_pl_cfg_in_db_scenario_2(local_infra, jf_session):
    """Test that playlist configuration is correctly mapped in the database."""
    # Scenario: JF already has a playlist and configuration matches the YT playlist by id to JF playlist by name
    truncate(PlaylistConfigResp)
    pl_cfg = PlaylistConfigResp(id=None,
                                jf_pl_id=None,
                                jf_pl_name='my_test_playlist',
                                ytm_pl_id='PL8xOIxSY5muApCYDDmUiKZyKMpdNMt-pM',
                                ytm_pl_name='WRONG_NAME',
                                jf_user_name='test',
                                sync=True)
    insert(pl_cfg)
    jf_pl = find_jf_playlist_by_name(pl_cfg.jf_pl_name)
    if jf_pl:
        jf_pl_id = jf_pl['Id']
        print("Found playlist")
    else:
        jf_pl_id = create_playlist(pl_cfg.jf_pl_name, find_user_by_name(pl_cfg.jf_user_name).id)
        print("Created playlist id=" + jf_pl_id)
    update_pl_cfg_in_db()
    cfgs = load_playlist_configs()
    print("Configs: " + str(len(cfgs)))
    pl_cfg_upd = cfgs[0]
    assert pl_cfg_upd.jf_pl_id == jf_pl_id, "JF playlist ID should match the existing JF playlist ID"


def test_sync_yt_into_jf_playlist(local_infra, jf_session, pl_sync_cfg_1, jf_user):
    """
    Test syncing a YT playlist into a JF playlist.

    Given:
        - A YT playlist with 3 songs
        - JF library has 2 of those songs downloaded
        - Only 1 of the 2 downloaded songs is currently in the JF playlist

    Expects:
        - The 1 downloaded song that's missing from the JF playlist gets added to it
        - The 1 song not in the JF library at all is returned as not_found (i.e. queued for download)
    """
    print(pl_sync_cfg_1.jf_pl_id)
    assert len(load_jf_playlist(pl_sync_cfg_1.jf_pl_id, jf_user.id, "ProviderIds")['Items']) == 1, "Before sync, only 1 song should be in the JF playlist"
    truncate(DownloadTask)
    sync_playlist(pl_sync_cfg_1.pl_cfg, jf_user)
    jf_playlist_songs = load_jf_playlist(pl_sync_cfg_1.jf_pl_id, jf_user.id, "ProviderIds")['Items']
    assert len(jf_playlist_songs) == 2, "After sync, there should be 2 songs in the JF playlist (the 1 that was already there + the 1 new one that was in the library)"
    assert set(s['ProviderIds']['YT'] for s in jf_playlist_songs) == set(pl_sync_cfg_1.situation.jf_lib_song_ids), "Only the songs that are in the JF library should be in the playlist after sync"
    dl_tasks = load_download_tasks()
    missing_yt_ids = list(set(pl_sync_cfg_1.situation.yt_pl_song_ids) - set(pl_sync_cfg_1.situation.jf_lib_song_ids))
    assert len(missing_yt_ids) == 1, "There should be exactly 1 song missing from the JF library for the test scenario to be valid"
    assert len(dl_tasks) == 1, "There should be 1 download task created for the song that was not in the JF library"
    assert dl_tasks[0].yt_id == missing_yt_ids[0], "The download task should be for the song that was not in the JF library"
    pass

def test_download_single_song(jf_session, local_infra, no_downloads):
    """Test downloading a single song from YT"""
    yt_id = "HzvDofigTKQ"
    assert reload_lib_until_song_found_n_times(yt_id, n=0)
    insert(DownloadTask(yt_id=yt_id))
    assert False == jf_has_song_with_yt_id(yt_id), "The song should not be in the library before download"
    process_download_tasks()
    dl_tasks = load_download_tasks()
    assert len(dl_tasks) == 1, "There should be 1 download task in the database"
    assert dl_tasks[0].status == "downloaded", "The download task should be marked as downloaded after processing"
    assert dl_tasks[0].path is not None, "The download task should have a file path after processing"
    assert reload_lib_until_song_found_n_times(yt_id, n=1), "The song should be in the library after download"
    # Assert file size is as expected
    # Remove the file after the test

@pytest.fixture
def pl_sync_cfg_1(docker_jf, jf_user):
    yt_pl_sync_1 = SimpleNamespace(id='PL8xOIxSY5muApCYDDmUiKZyKMpdNMt-pM')
    song_ids = [song['id'] for song in load_flat_playlist(yt_pl_sync_1.id)['entries']]
    assert len(song_ids) == 3, "YT playlist should have 3 songs for the test"
    pl_id = create_playlist('test_sync_1', jf_user.id, type="Audio")
    truncate(PlaylistConfigResp)
    try:
        imported_yt_songs = song_ids[:2]
        for sid in imported_yt_songs:
            copy_single_file_into_docker_container(docker_jf, f"{Config.JellyFin.music_lib_dir}/ytid_{sid}_ytid.m4a", Config.TestData.sample_media)
        reload_library()
        jf_songs = load_all_items("Audio", "Path,ProviderIds")
        for sid in imported_yt_songs:
            jf_id = next((s['Id'] for s in jf_songs if sid in s['Path']), None)
            if jf_id:
                jf_item_full = load_item_by_id(jf_id, jf_user.id)
                jf_item_full['ProviderIds']['YT'] = sid
                assert save_item(jf_item_full), f"Failed to update JF item with YT id {sid}"
        frst_id = next((s['Id'] for s in jf_songs if song_ids[0] in s['Path']), None)
        add_media_ids_to_playlist(pl_id, [frst_id], jf_user.id)
        pl_cfg = PlaylistConfigResp(id=None,
                                    jf_pl_id=pl_id,
                                    jf_pl_name='test_sync_1',
                                    ytm_pl_id=yt_pl_sync_1.id,
                                    ytm_pl_name='WRONG_NAME',
                                    jf_user_name='test',
                                    sync=True)
        pl_cfg.id = insert(pl_cfg)
        yield SimpleNamespace(yt_pl=yt_pl_sync_1, jf_pl_id=pl_id, pl_cfg=pl_cfg, situation=SimpleNamespace(yt_pl_song_ids=song_ids, jf_lib_song_ids=imported_yt_songs))
    finally:
        remove_jf_playlist(pl_id)
        delete(pl_cfg)
