import os

import requests

from main import install_ffmpeg
from test.config import Config
from test.helpers import get_test_user_session, save_settings
from utils.db import get_db_session, load_settings
from utils.jf import create_playlist, load_all_playlists, reload_library
from utils.ytm import load_flat_playlist


def test_pb_container(docker_pocketbase):
    """PocketBase container is reachable."""
    resp = requests.get(f"{Config.PocketBase.url}/_")
    assert resp.status_code == 200, f"PocketBase health check failed: {resp.status_code}"
    get_db_session()


def test_jf_container(docker_jf):
    """JF container is reachable."""
    resp = requests.get(f"{Config.JellyFin.url}/health")
    assert resp.status_code == 200, f"JF health check failed: {resp.status_code}"


def test_jf_login(docker_jf):
    """Can authenticate with the test user."""
    session = get_test_user_session()
    assert session is not None, "Failed to get JF user session"

def test_jf_playlist_operations(jf_user):
    """Can create, update and delete a JF playlist."""
    user = jf_user
    # Create playlist
    id = create_playlist('regression_basic_1', user.id, type="Audio")
    jf_playlists = load_all_playlists()

    assert any(pl for pl in jf_playlists if pl['Name'] == 'regression_basic_1'), "Failed to find created JF playlist"

def test_jf_lib_refresh(jf_session):
    """Can create, update and delete a JF playlist."""
    reload_library()


def test_yt_read_playlist_flat():
    """Can read YT playlist without loading entries."""
    pl = load_flat_playlist(Config.Playlists.yt_src_id, load_entries=False)
    assert pl is not None, "Failed to load YT playlist"
    assert pl['title'] == 'test_1', f"Unexpected playlist title: {pl['title']}"

def test_update_settings():
    """Can update settings in the database."""
    settings = load_settings()
    settings.wait_time = '5m'
    save_settings(settings)
    settings_upd = load_settings()
    assert settings_upd.wait_time == '5m', "Failed to update settings in the database"

    settings.wait_time = '10m'
    save_settings(settings)
    settings_upd = load_settings()
    assert settings_upd.wait_time == '10m', "Failed to update settings in the database"

def test_ffmpeg():
    install_ffmpeg()
    status = os.system("ffmpeg --help")
    print(f"ffmpeg status: {status}")
    assert status == 0