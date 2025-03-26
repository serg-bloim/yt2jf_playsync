import os
import time
from enum import auto, StrEnum

import yt_dlp
from pyyoutube import Client
from ytmusicapi import YTMusic, OAuthCredentials
from ytmusicapi.auth.oauth.models import BaseTokenDict

from utils.db import GUser, save_guser


def load_flat_playlist(playlist_id, load_entries=True):
    URL = f'https://music.youtube.com/playlist?list={playlist_id}'
    ydl_opts = {'extract_flat': True}

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(URL, download=False, process=load_entries)
        # ℹ️ ydl.sanitize_info makes the info json-serializable
        return ydl.sanitize_info(info)
    pass

class Category(StrEnum):
    VIDEO = auto()
    SONG = auto()

class StaticOAuthCredentials(OAuthCredentials):
    def __init__(self, client_id: str, client_secret: str, access_token: str):
        super().__init__(client_id, client_secret, None, None)
        self.access_token = access_token

    def refresh_token(self, refresh_token: str) -> BaseTokenDict:
        return BaseTokenDict(access_token=self.access_token,
                             expires_in=100000,
                             scope="https://www.googleapis.com/auth/youtube.readonly",
                             token_type="Bearer")


def createYtMusic(access_token, refresh_token):
    client_id = os.getenv('GOOGLE_APP_CLIENT_ID')
    client_secret = os.getenv('GOOGLE_APP_CLIENT_SECRET')
    credentials = StaticOAuthCredentials(
        client_id=client_id,
        client_secret=client_secret,
        access_token=access_token)

    auth = {'scope': '',
            'token_type': 'Bearer',
            'access_token': access_token,
            'refresh_token': refresh_token}
    return YTMusic(auth=auth, oauth_credentials=credentials)


def refresh_access_token(usr: GUser):
    client_id = os.getenv('GOOGLE_APP_CLIENT_ID')
    client_secret = os.getenv('GOOGLE_APP_CLIENT_SECRET')
    client = Client(client_id=client_id, client_secret=client_secret, refresh_token=usr.refresh_token)
    tkn = client.refresh_access_token(usr.refresh_token)
    usr.access_token = tkn.access_token
    usr.access_token_expires = int(time.time()) + tkn.expires_in
    save_guser(usr)
    return tkn
