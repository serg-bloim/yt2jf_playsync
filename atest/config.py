import json
import os

from pyyoutube import AccessToken

from utils.common import root_dir


def read_token():
    with open(root_dir() / 'atest/token.json') as f:
        data = json.load(f)
    return AccessToken(**data)

class Config:
    class TestUser:
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


os.environ['CONFIG_DB_URL'] = Config.PocketBase.url
os.environ['CONFIG_DB_AUTH_USER'] = Config.PocketBase.username
os.environ['CONFIG_DB_AUTH_PWD'] = Config.PocketBase.password
