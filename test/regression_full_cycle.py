import time

import pytest

from main import main
from test.helpers import truncate, save_settings, retry_on_exception, jf_has_song_with_yt_id
from test.regression import pl_sync_cfg_1
from utils.db import load_download_tasks, DownloadTask, load_settings
from utils.jf import load_jf_playlist, reload_library, load_all_items


def test_main(local_infra, jf_user, pl_sync_cfg_1, no_wait, no_downloads):
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
    reload_library()
    assert len(load_all_items("Audio", "Path")) == 2, "Before sync, there should be 2 songs in the JF library"
    assert len(load_jf_playlist(pl_sync_cfg_1.jf_pl_id, jf_user.id, "ProviderIds")['Items']) == 1, "Before sync, only 1 song should be in the JF playlist"

    main()

    def checks1():
        reload_library()
        jf_playlist_songs = load_jf_playlist(pl_sync_cfg_1.jf_pl_id, jf_user.id, "ProviderIds")['Items']
        assert len(jf_playlist_songs) == 2, "After sync, there should be 2 songs in the JF playlist (the 1 that was already there + the 1 new one that was in the library)"
        assert set(s['ProviderIds']['YT'] for s in jf_playlist_songs) == set(pl_sync_cfg_1.situation.jf_lib_song_ids), "Only the songs that are in the JF library should be in the playlist after sync"
        dl_tasks = load_download_tasks()
        missing_yt_ids = list(set(pl_sync_cfg_1.situation.yt_pl_song_ids) - set(pl_sync_cfg_1.situation.jf_lib_song_ids))
        assert len(missing_yt_ids) == 1, "There should be exactly 1 song missing from the JF library for the test scenario to be valid"
        assert len(dl_tasks) == 1, "There should be 1 download task created for the song that was not in the JF library"
        assert dl_tasks[0].yt_id == missing_yt_ids[0], "The download task should be for the song that was not in the JF library"
        assert dl_tasks[0].status == 'downloaded', "The download task should be marked as downloaded after processing"
        assert jf_has_song_with_yt_id(dl_tasks[0].yt_id)
    retry_on_exception(checks1)

    main()

    def checks2():
        reload_library()
        jf_playlist_songs = load_jf_playlist(pl_sync_cfg_1.jf_pl_id, jf_user.id, "ProviderIds")['Items']
        assert len(jf_playlist_songs) == 3, "After sync, there should be 3 songs in the JF playlist (the 1 that was already there + the 1 new one that was in the library + the 1 that was downloaded in the previous step)"
    retry_on_exception(checks2)
    pass

@pytest.fixture
def no_wait():
    settings = load_settings()
    old_wait_time = settings.wait_time
    settings.wait_time="0s"
    save_settings(settings)
    yield None
    settings = load_settings()
    settings.wait_time = old_wait_time
    save_settings(settings)
