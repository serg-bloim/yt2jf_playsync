import json
import os

from pyyoutube import AccessToken

from utils.common import root_dir


def read_token():
    with open(root_dir() / 'test/token.json') as f:
        data = json.load(f)
    return AccessToken(**data)

class Config:
    class JellyFin:
        username = 'test'

    class TestUser:
        jf_username = 'Test'
        jf_pw = 'qwaszx'
        google_user = os.getenv('GOOGLE_USER_ID')
        slack_id = 'UFZPMKLKC'

    class PocketBase:
        username = 'abc@test.com'
        password = 'testtest'
        image = 'vicknesh/pocketbase'
        container_name = 'playsync_pocketbase_test_db'
        port = '38080'
        port_mapping = {'8080': port}
        url = f"http://localhost:{port}"

    class Playlists:
        yt_src_id = 'PL8xOIxSY5muApCYDDmUiKZyKMpdNMt-pM'
        yt_dst_id = 'VLPL8xOIxSY5muBt5Rpz5m86S_tjsr1xB9-N'

    google_token = read_token()

def update_envvar():
    os.environ['CONFIG_DB_URL'] = Config.PocketBase.url
    os.environ['CONFIG_DB_AUTH_USER'] = Config.PocketBase.username
    os.environ['CONFIG_DB_AUTH_PWD'] = Config.PocketBase.password

    os.environ['DEFAULT_PF2JF_PATH_CONV_SEARCH'] = '^/downloads'
    os.environ['DEFAULT_PF2JF_PATH_CONV_REPLACE'] = '/data'
    os.environ['DEFAULT_PF2JF_YTID_REGEX'] = '(?<=_)(?P<id>.{11,})(?=\.[^\.]+$)'
    os.environ['DEFAULT_JF_USER_NAME'] = 'test'