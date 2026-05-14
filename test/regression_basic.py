import requests

from test.config import Config
from test.helpers import get_test_user_session
from utils.db import get_db_session


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