import os

from pyyoutube import Client

from sync import SLACK_CHANNEL_INFO
from utils import slack
from utils.db import load_guser_by_id, load_gusers, GUser


def relogin_users():
    users = load_gusers()
    for usr in users:
        relogin_user(usr)


def relogin_user(usr: GUser):
    ytc = Client(client_id=os.getenv('GOOGLE_APP_CLIENT_ID'), client_secret=os.getenv('GOOGLE_APP_CLIENT_SECRET'))
    url = ytc.get_authorize_url()
    slack.send_ephemeral(f"Login to google <{url}|Google OAuth2 login>", SLACK_CHANNEL_INFO, usr.slack_user)

