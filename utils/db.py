import dataclasses
from collections import defaultdict
import os
from dataclasses import asdict
from functools import lru_cache

import requests

from utils.common import get_nested_value
from utils.logs import create_logger


@dataclasses.dataclass
class __DBConfig:
    url = os.getenv('CONFIG_DB_URL')
    auth_collection = os.getenv('CONFIG_DB_auth_collection', '_superusers')
    auth_user = os.getenv('CONFIG_DB_AUTH_USER')
    auth_pwd = os.getenv('CONFIG_DB_AUTH_PWD')


__config = __DBConfig()


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

logger = create_logger("db")


@lru_cache(maxsize=1)
def db_auth():
    logger.info("Authenticating")
    url = f"{__config.url}/api/collections/{__config.auth_collection}/auth-with-password"
    response = requests.post(url, data={
        'identity': __config.auth_user,
        'password': __config.auth_pwd
    })
    if response:
        logger.info("Successfully authenticated.")
        return response.json()['token']
    else:
        logger.error(f"Failed to authenticate. Status: {response.status_code}, Response:{response.json()}")


__db_session = requests.session()
__db_session.headers.update({'Authorization': db_auth()})


def std_fields():
    return [
        {
            "hidden": False,
            "name": "created",
            "onCreate": True,
            "onUpdate": False,
            "presentable": False,
            "system": False,
            "type": "autodate"
        },
        {
            "hidden": False,
            "name": "updated",
            "onCreate": True,
            "onUpdate": True,
            "presentable": False,
            "system": False,
            "type": "autodate"
        }
    ]


def set_setting_if_absent(key, val):
    url = f"{__config.url}/api/collections/yt_sync_settings/records"
    resp = __db_session.post(url, data={'key': key, 'val': val})
    http_code = resp.status_code
    if resp:
        logger.debug(f"Added setting '{key}={val}'")
    elif http_code == 400 and get_nested_value(resp.json(), "data", "key", "code") == 'validation_not_unique':
        logger.debug(f"Setting '{key}' already exists")
    else:
        resp.raise_for_status()


def create_db_structure():
    def create_collection(name, fields, list_rule=None, view_rule=None, create_rule=None, update_rule=None,
                          delete_rule=None):
        unique_keys = defaultdict(list)
        for f in fields:
            key = f.get('unique_key')
            if key:
                unique_keys[key].append(f['name'])
        indexes = [f"CREATE UNIQUE INDEX `{name}_{k}` ON `{name}` ({','.join(f'`{f}`' for f in fields)})"
                   for k, fields in
                   unique_keys.items()]
        dscr = {
            'name': name,
            'fields': std_fields() + fields,
            'indexes': indexes,
            'listRule': list_rule,
            'viewRule': view_rule,
            'createRule': create_rule,
            'updateRule': update_rule,
            'deleteRule': delete_rule,
        }
        resp = __db_session.post(f"{__config.url}/api/collections", json=dscr)
        if resp:
            return resp.json()
        elif resp.status_code == 400 and get_nested_value(resp.json(), 'data', 'name', 'code') == 'validation_collection_name_exists':
            logger.debug(f"Collection `{name}` already exists")
        else:
            resp.raise_for_status()

    def detect_type(field):
        if field.type == str:
            return 'text'
        elif field.type == bool:
            return 'bool'
        elif field.type == int:
            return 'number'
        raise ValueError("Cannot detect a db field type from field: " + field)

    def parse_dataclass(dc):
        return [
            {
                'name': field.name,
                'type': detect_type(field),
                'unique_key': field.metadata.get('unique_key'),
            } for field
            in dc.__dataclass_fields__.values()
            if field.name != 'id'
        ]

    create_collection('playlist_config', parse_dataclass(PlaylistConfigResp))
    create_collection('yt_media_mapping', parse_dataclass(MediaMappingResp), create_rule='')
    settings_fields = [{'name': 'key', 'type': 'text', 'unique_key': 'settings_idx_uniq_key'}, {'name': 'val', 'type': 'text'}]
    create_collection('yt_sync_settings', settings_fields)

    set_setting_if_absent('pf2jf_path_conv_search', os.getenv('DEFAULT_PF2JF_PATH_CONV_SEARCH'))
    set_setting_if_absent('pf2jf_path_conv_replace', os.getenv('DEFAULT_PF2JF_PATH_CONV_REPLACE'))
    set_setting_if_absent('jf_user_name', os.getenv('DEFAULT_JF_USER_NAME'))
    set_setting_if_absent('wait_time', os.getenv('DEFAULT_WAIT_TIME', '24h'))


@lru_cache(maxsize=1)
def load_playlist_configs():
    url = f"{__config.url}/api/collections/playlist_config/records"
    response = __db_session.get(url)
    if response:
        return [PlaylistConfigResp(**{k: v for k, v in pl.items() if k in PlaylistResp_allowed_fields}) for pl in
                response.json()['items']]


def save_playlist_config(pl_config: PlaylistConfigResp):
    url = f"{__config.url}/api/collections/playlist_config/records/{pl_config.id}"
    response = __db_session.patch(url, json=asdict(pl_config))
    response.raise_for_status()


def load_media_mappings():
    url = f"{__config.url}/api/collections/yt_media_mapping/records"

    def load_page(page_n=1):
        params = {"page": page_n, "perPage": 100}
        response = __db_session.get(url, params=params)
        if response:
            json = response.json()
            mappings = [MediaMappingResp(**{k: v for k, v in pl.items() if k in MediaMappingResp_allowed_fields}) for pl
                        in json['items']]
            return mappings, json['page'], json['totalPages'], json['totalItems']

    first_page, page_n, total_pages, total_items = load_page()
    all_mappings = []
    all_mappings += first_page
    while page_n < total_pages:
        mappings, page_n, total_pages, total_items = load_page(page_n + 1)
        all_mappings += mappings

    return all_mappings


def delete_mapping(mapping: MediaMappingResp):
    url = f"{__config.url}/api/collections/yt_media_mapping/records/{mapping.id}"
    response = __db_session.delete(url)
    response.raise_for_status()


@dataclasses.dataclass
class Settings:
    pf2jf_path_conv_search: str
    pf2jf_path_conv_replace: str
    jf_user_name: str
    jf_extract_ytid_regex: str
    wait_time: str = "1m"


@lru_cache(maxsize=1)
def load_settings():
    url = f"{__config.url}/api/collections/yt_sync_settings/records"
    response = __db_session.get(url)
    allowed_fields = {field.name for field in Settings.__dataclass_fields__.values()}
    if response:
        data = {entry['key']: entry['val'] for entry in response.json()['items']}
        return Settings(**{k: v for k, v in data.items() if k in allowed_fields})
