import json
import os
import webbrowser
from dataclasses import asdict

from pyyoutube import Client

from test.helpers import refresh_access_token
from oauth import relogin_users
from utils.common import root_dir
from utils.web import run_auth_server


def test_send_link_all_users():
    relogin_users()


def test_login(capsys):
    ytc = Client(client_id=os.getenv('GOOGLE_APP_CLIENT_ID'), client_secret=os.getenv('GOOGLE_APP_CLIENT_SECRET'))
    authorize_url, app_name = ytc.get_authorize_url(scope=['https://www.googleapis.com/auth/youtube', 'https://www.googleapis.com/auth/userinfo.profile'],
                                                    redirect_uri='https://localhost:1234/abc',
                                                    state='abc',
                                                    prompt="consent")
    with capsys.disabled():
        print(authorize_url)
    webbrowser.open(authorize_url)
    token = run_auth_server(ytc)
    with open(root_dir() / 'test/token.json', 'w') as f:
        json.dump(asdict(token), f, indent=2)


def test_refresh(capsys):
    refresh_access_token()