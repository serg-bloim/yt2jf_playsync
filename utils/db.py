import dataclasses
import os
from dataclasses import asdict
from functools import lru_cache

import requests

config_db_url = os.getenv('CONFIG_DB_URL')


@dataclasses.dataclass
class PlaylistConfigResp:
    id: str
    jf_pl_id: str
    jf_pl_name: str
    ytm_pl_id: str
    ytm_pl_name: str
    jf_user_name: str
    sync: bool


@dataclasses.dataclass
class MediaMappingResp:
    id: str
    yt_id: str
    yt_playlist_id: str
    local_path: str
    jf_id: str


PlaylistResp_allowed_fields = {field.name for field in PlaylistConfigResp.__dataclass_fields__.values()}
MediaMappingResp_allowed_fields = {field.name for field in MediaMappingResp.__dataclass_fields__.values()}


@lru_cache(maxsize=1)
def load_playlist_configs():
    url = f"{config_db_url}/api/collections/playlist_config/records"
    response = requests.get(url)
    if response:
        return [PlaylistConfigResp(**{k: v for k, v in pl.items() if k in PlaylistResp_allowed_fields}) for pl in response.json()['items']]


def save_playlist_config(pl_config: PlaylistConfigResp):
    url = f"{config_db_url}/api/collections/playlist_config/records/{pl_config.id}"
    response = requests.patch(url, json=asdict(pl_config))
    response.raise_for_status()


def load_media_mappings():
    url = f"{config_db_url}/api/collections/yt_media_mapping/records"

    def load_page(page_n=1):
        params = {"page": page_n, "perPage": 100}
        response = requests.get(url, params=params)
        if response:
            json = response.json()
            mappings = [MediaMappingResp(**{k: v for k, v in pl.items() if k in MediaMappingResp_allowed_fields}) for pl in json['items']]
            return mappings, json['page'], json['totalPages'], json['totalItems']

    first_page, page_n, total_pages, total_items = load_page()
    all_mappings = []
    all_mappings += first_page
    while page_n < total_pages:
        mappings, page_n, total_pages, total_items = load_page(page_n + 1)
        all_mappings += mappings

    return all_mappings


def delete_mapping(mapping: MediaMappingResp):
    url = f"{config_db_url}/api/collections/yt_media_mapping/records/{mapping.id}"
    response = requests.delete(url)
    response.raise_for_status()


@dataclasses.dataclass
class Settings:
    pf2jf_path_conv_search: str
    pf2jf_path_conv_replace: str
    jf_user_name: str
    wait_time: str = "1m"


@lru_cache(maxsize=1)
def load_settings():
    url = f"{config_db_url}/api/collections/yt_sync_settings/records"
    response = requests.get(url)
    allowed_fields = {field.name for field in Settings.__dataclass_fields__.values()}
    if response:
        data = {entry['key']: entry['val'] for entry in response.json()['items']}
        return Settings(**{k: v for k, v in data.items() if k in allowed_fields})
