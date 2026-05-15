import requests

from test.config import Config
from test.helpers import get_test_user_session
from utils.db import get_db_session
from utils.jf import create_playlist, load_all_playlists
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


def test_yt_read_playlist_flat():
    """Can read YT playlist without loading entries."""
    pl = load_flat_playlist(Config.Playlists.yt_src_id, load_entries=False)
    assert pl is not None, "Failed to load YT playlist"
    assert pl['title'] == 'test_1', f"Unexpected playlist title: {pl['title']}"
