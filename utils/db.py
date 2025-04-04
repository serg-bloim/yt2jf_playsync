import dataclasses
import os
import time
from collections import defaultdict
from dataclasses import asdict
from dataclasses import field
from datetime import datetime
from enum import Enum, auto
from functools import lru_cache
from typing import List, Tuple, TypeVar

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


@dataclasses.dataclass
class LocalMediaArchive:
    id: str
    created: datetime = field(metadata={'ignore': True})
    jf_id: str = field(metadata={'unique_key': True})
    local_path: str
    exists: bool


@dataclasses.dataclass
class YtMediaMetadata:
    id: str
    yt_id: str = field(metadata={'unique_key': True})
    title: str
    artist: str
    category: str
    album_name: str = ''
    duration: int = 0
    views_cnt: int = 0
    thumbnail_url: str = ''
    alt_id: str = None
    ignore: bool = False
    col_name = 'yt_media_metadata'


@dataclasses.dataclass
class YtAutomatedPlaylist:
    yt_pl_id: str
    yt_user: str
    enabled: bool = False
    vsd_replace_in_src: bool = False
    vsd_replace_during_copy: bool = False
    copy: bool = False
    copy_dst: str = None
    comment: str = None
    col_name = 'yt_automated_playlist'


@dataclasses.dataclass
class GUser:
    id: str
    yt_user_id: str = field(metadata={'unique_key': True})
    yt_username: str
    slack_user: str = None
    access_token: str = None
    access_token_expires: int = None
    refresh_token: str = None
    refresh_token_expires: int = None
    comment: str = None
    col_name = 'google_user'

    def is_refresh_token_valid(self):
        return self.refresh_token and self.refresh_token_expires > time.time()

    def is_access_token_valid(self):
        return self.access_token and self.access_token_expires > time.time()


class CreateOpResult(Enum):
    CREATED = auto()
    DUPLICATE = auto()
    ERROR = auto()


def calc_allowed_fields(clazz) -> Tuple:
    return tuple(field.name for field in dataclasses.fields(clazz))


PlaylistResp_allowed_fields = calc_allowed_fields(PlaylistConfigResp)
MediaMappingResp_allowed_fields = calc_allowed_fields(MediaMappingResp)
LocalMediaArchive_allowed_fields = calc_allowed_fields(LocalMediaArchive)

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
        elif resp.status_code == 400 and get_nested_value(resp.json(), 'data', 'name',
                                                          'code') == 'validation_collection_name_exists':
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
                'unique_key': parse_unique_key(field),
            } for field
            in dataclasses.fields(dc)
            if not (field.name == 'id' or field.metadata.get("ignore"))
        ]

    def parse_unique_key(field):
        v = field.metadata.get('unique_key')
        if isinstance(v, bool):
            v = field.name
        return v

    create_collection('playlist_config', parse_dataclass(PlaylistConfigResp))
    create_collection('yt_media_mapping', parse_dataclass(MediaMappingResp), create_rule='')
    settings_fields = [{'name': 'key', 'type': 'text', 'unique_key': 'settings_idx_uniq_key'},
                       {'name': 'val', 'type': 'text'}]
    create_collection('yt_sync_settings', settings_fields)
    create_collection('local_media_archive', parse_dataclass(LocalMediaArchive))
    models = [YtMediaMetadata, YtAutomatedPlaylist, GUser]
    for model in models:
        create_collection(model.col_name, parse_dataclass(model))

    set_setting_if_absent('pf2jf_path_conv_search', os.getenv('DEFAULT_PF2JF_PATH_CONV_SEARCH'))
    set_setting_if_absent('pf2jf_path_conv_replace', os.getenv('DEFAULT_PF2JF_PATH_CONV_REPLACE'))
    set_setting_if_absent('jf_user_name', os.getenv('DEFAULT_JF_USER_NAME'))
    set_setting_if_absent('wait_time', os.getenv('DEFAULT_WAIT_TIME', '24h'))
    set_setting_if_absent('last_local_media_update_ts', 0)


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


def load_all_paged_records(url, filter=None):
    def load_page(page_n=1):
        params = {"page": page_n, "perPage": 100, "filter": filter}
        response = __db_session.get(url, params=params)
        if response:
            json = response.json()
            return json['items'], json['page'], json['totalPages'], json['totalItems']

    first_page, page_n, total_pages, total_items = load_page()
    all_items = []
    all_items += first_page
    while page_n < total_pages:
        page_items, page_n, total_pages, total_items = load_page(page_n + 1)
        all_items += page_items
    return all_items


def load_media_mappings():
    url = f"{__config.url}/api/collections/yt_media_mapping/records"
    recs = load_all_paged_records(url)
    return [MediaMappingResp(**{k: v for k, v in pl.items() if k in MediaMappingResp_allowed_fields}) for pl in recs]


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
    last_local_media_update_ts: int = 0


@lru_cache(maxsize=1)
def load_settings():
    url = f"{__config.url}/api/collections/yt_sync_settings/records"
    response = __db_session.get(url)
    allowed_fields = {field.name for field in dataclasses.fields(Settings)}
    if response:
        data = {entry['key']: entry['val'] for entry in response.json()['items']}
        return Settings(**{k: v for k, v in data.items() if k in allowed_fields})


def load_local_media():
    url = f"{__config.url}/api/collections/local_media_archive/records"
    recs = load_all_paged_records(url)
    items = [LocalMediaArchive(**{k: v for k, v in pl.items() if k in LocalMediaArchive_allowed_fields}) for pl in recs]
    for itm in items:
        itm.created = datetime.fromisoformat(itm.created)
    return items


def add_local_media(items: List[dict]):
    url = f"{__config.url}/api/collections/local_media_archive/records"
    for itm in items:
        try:
            resp = __db_session.post(url, data={'jf_id': itm['Id'], 'local_path': itm.get('Path'), 'exists': True})
            http_code = resp.status_code
            if resp:
                logger.debug(f"Added LocalMediaArchive '{itm['Id']}/{itm['Name']}'")
            elif http_code == 400 and get_nested_value(resp.json(), "data", "key", "code") == 'validation_not_unique':
                logger.debug(f"Setting '{itm['Id']}/{itm['Name']}' already exists")
            else:
                resp.raise_for_status()
        except:
            logger.exception(f"Cannot save a LocalMediaArchive entry '{itm['Id']}/{itm['Name']}'")


def load_yt_media_metadata(allowed_fields=calc_allowed_fields(YtMediaMetadata), **filters):
    def decorate(v):
        if v is None:
            return 'null'
        return f"'{v}'"

    filter = " && ".join(f"{k} = {decorate(v)}" for k, v in filters.items())
    if filter:
        filter = f"({filter})"
    url = f"{__config.url}/api/collections/yt_media_metadata/records"
    recs = load_all_paged_records(url, filter=filter)
    items = [YtMediaMetadata(**{k: v for k, v in pl.items() if k in allowed_fields}) for pl in recs]
    return items


def create_yt_media_metadata(media_metadata: YtMediaMetadata) -> CreateOpResult:
    url = f"{__config.url}/api/collections/yt_media_metadata/records"
    try:
        resp = __db_session.post(url, data=asdict(media_metadata))
        http_code = resp.status_code
        if resp:
            logger.debug(f"Added YtMediaMetadata '{media_metadata.yt_id}/{media_metadata.title}'")
            return CreateOpResult.CREATED
        elif http_code == 400 and get_nested_value(resp.json(), "data", "yt_id", "code") == 'validation_not_unique':
            logger.debug(f"YtMediaMetadata '{media_metadata.yt_id}/{media_metadata.title}' already exists")
            return CreateOpResult.DUPLICATE
        else:
            resp.raise_for_status()
    except:
        logger.exception(f"Cannot save a YtMediaMetadata '{media_metadata.yt_id}/{media_metadata.title}'")
    return CreateOpResult.ERROR


def save_yt_media_metadata(mm: YtMediaMetadata):
    url = f"{__config.url}/api/collections/{mm.col_name}/records/{mm.id}"
    response = __db_session.patch(url, json=asdict(mm))
    response.raise_for_status()


def load_yt_automated_playbooks(allowed_fields=calc_allowed_fields(YtAutomatedPlaylist)):
    url = f"{__config.url}/api/collections/{YtAutomatedPlaylist.col_name}/records"
    recs = load_all_paged_records(url)
    items = [YtAutomatedPlaylist(**filter_fields(pl, allowed_fields)) for pl in recs]
    return items


def load_gusers(allowed_fields=calc_allowed_fields(GUser)) -> list[GUser]:
    return load_all_db_objects(GUser)


T = TypeVar('T')


def load_all_db_objects(db_clazz: type[T]) -> list[T]:
    allowed_fields = calc_allowed_fields(db_clazz)
    url = f"{__config.url}/api/collections/{db_clazz.col_name}/records"
    recs = load_all_paged_records(url)
    items = [db_clazz(**filter_fields(pl, allowed_fields)) for pl in recs]
    return items


def load_guser_by_id(guid: str, allowed_fields=calc_allowed_fields(GUser)) -> GUser:
    url = f"{__config.url}/api/collections/{GUser.col_name}/records"
    params = {'filter': f"yt_user_id='{guid}'"}
    resp = __db_session.get(url, params=params)
    if resp.status_code == 200:
        items = resp.json()['items']
        if len(items) == 1:
            itm = items[0]
            return GUser(**filter_fields(itm, allowed_fields))


def save_guser(user: GUser):
    url = f"{__config.url}/api/collections/{user.col_name}/records/{user.id}"
    response = __db_session.patch(url, json=asdict(user))
    response.raise_for_status()


def filter_fields(d, fields):
    return {k: v for k, v in d.items() if k in fields}
