import os
import shutil
from contextlib import contextmanager
from pathlib import Path
from time import sleep

import docker
import pytest
import requests
import waiting
from docker.types import Mount

import main
from test.config import Config
from test.helpers import populate_db, get_test_user_session, requests_retry_session, setup_jf_library, truncate
from utils import db
from utils.db import get_db_session, DownloadTask
from utils.jf import get_current_user


@contextmanager
def managed_container(docker_client, image, container_name, ports=None, mounts=None, express_mode=False):
    old_container = next((c for c in docker_client.containers.list(all=True) if c.name == container_name), None)
    if express_mode and old_container and old_container.status == 'running':
        print(f"{container_name} is already running in express mode")
        container = old_container
    else:
        print(f"Running container {container_name}")
        if old_container:
            old_container.remove(force=True)
        container = docker_client.containers.run(image,
                                                 name=container_name,
                                                 detach=True,
                                                 ports=ports,
                                                 mounts=mounts)
    try:
        yield container
    finally:
        if not express_mode:
            print(f"Removing container {container_name}")
            container.remove(force=True)


@pytest.fixture(scope='session')
def docker_client():
    current_ctx = docker.context.Context.load_context(docker.context.api.get_current_context_name())
    url = current_ctx.endpoints["docker"]["Host"]
    docker_client = docker.DockerClient(base_url=url)
    try:
        yield docker_client
    finally:
        docker_client.close()


@pytest.fixture(scope='session')
def docker_pocketbase(docker_client):
    with managed_container(docker_client,
                           Config.PocketBase.image,
                           Config.PocketBase.container_name,
                           ports=Config.PocketBase.port_mapping,
                           express_mode=Config.express_mode) as db_container:
        def predicate():
            requests.get(Config.PocketBase.url + "/_").raise_for_status()
            return True

        sleep(1)
        waiting.wait(predicate,
                     expected_exceptions=requests.exceptions.ConnectionError,
                     timeout_seconds=60)
        sleep(1)
        try:
            get_db_session()
        except:
            code, out = db_container.exec_run(
                f'/bin/pocketbase --dir /exia/pocketbase --hooksDir /exia/pocketbase_hooks --publicDir /exia/pocketbase_public superuser upsert {Config.PocketBase.username} {Config.PocketBase.password}')
            assert code == 0
            print(out.decode())
            db.create_db_structure()
            populate_db()
        yield db_container


@pytest.fixture(scope='session')
def docker_jf(docker_client):
    dwld_dir = str(Config.TestData.download_mount_dir)
    os.makedirs(dwld_dir, exist_ok=True)
    with managed_container(docker_client,
                           Config.JellyFin.image,
                           Config.JellyFin.container_name,
                           ports={'8096/tcp': int(Config.JellyFin.port)},
                           mounts=[Mount(
                                 target='/data/music/dwld',
                                 source=dwld_dir,
                                 type='bind',
                                 read_only=False
                           )],
                           express_mode=Config.express_mode) as jf:
        def predicate():
            requests.get(f"{Config.JellyFin.url}/health").raise_for_status()
            return True
        jf.exec_run(f"mkdir -p {Config.JellyFin.music_lib_dir}")
        sleep(1)
        waiting.wait(predicate,
                     expected_exceptions=(requests.exceptions.ConnectionError, requests.exceptions.HTTPError),
                     timeout_seconds=60,
                     sleep_seconds=2)
        try:
            get_test_user_session()
        except:
            session = requests_retry_session(retries=5, status_forcelist=list(range(500, 505)))
            resp = session.get(f"{Config.JellyFin.url}/Startup/Configuration")
            resp.raise_for_status()
            init_cfg = resp.json()
            init_cfg["ServerName"] = "Test server"
            requests.post(f"{Config.JellyFin.url}/Startup/Configuration", json=init_cfg).raise_for_status()
            requests.get(f"{Config.JellyFin.url}/Startup/User").raise_for_status()
            requests.post(f"{Config.JellyFin.url}/Startup/User",
                          json={"Name": Config.TestUser.jf_username, "Password": Config.TestUser.jf_pw}).raise_for_status()
            requests.post(f"{Config.JellyFin.url}/Startup/Complete").raise_for_status()
            setup_jf_library()

        yield jf

@pytest.fixture(scope='session')
def jf_session(docker_jf):
    return get_test_user_session()


@pytest.fixture(scope='session')
def jf_user(jf_session):
    return get_current_user()

@pytest.fixture(scope='session')
def local_infra(docker_pocketbase, docker_jf):
    return (docker_pocketbase, docker_jf)

@pytest.fixture
def no_downloads():
    truncate(DownloadTask)
    dwld_dir = Path(os.environ['CONFIG_YTD_ROOT_DIR'])
    shutil.rmtree(dwld_dir, ignore_errors=True)

@pytest.fixture
def ffmpeg():
    main.install_ffmpeg()