import dataclasses

from jellyfin_apiclient_python import JellyfinClient

from utils.common import chunked
from utils.logs import create_logger

client = JellyfinClient()
import requests

__session__ = requests.Session()
__session__.headers.update({"X-Emby-Token": "c01d7abab8e84d128ad101753a41dead"})
__jf_url__ = "http://192.168.1.100:8096"
logger = create_logger("jellyfin_client")

def get_jf_base_url():
    return __jf_url__

def load_jf_playlist(pl_id, user_id, fields=""):
    fields_str = fields
    if not isinstance(fields_str, str):
        fields_str = ",".join(fields_str)
    resp = __session__.get(f"{__jf_url__}/Playlists/{pl_id}/Items", params={'UserId': user_id, "Fields": fields_str})
    if resp:
        data = resp.json()
        return data


def load_all_items(types="", fields=""):
    types_str = types
    if not isinstance(types_str, str):
        types_str = ",".join(types)
    fields_str = fields
    if not isinstance(fields_str, str):
        fields_str = ",".join(fields_str)
    params = {'IncludeItemTypes': types_str,
              "Fields": fields_str,
              "Recursive": "true"}
    resp = __session__.get(f"{__jf_url__}/Items/", params=params)
    if resp:
        data = resp.json()['Items']
        return data


def load_item_by_id(id, user_id=""):
    params = {"UserId": user_id}
    resp = __session__.get(f"{__jf_url__}/Items/{id}", params=params)
    if resp:
        return resp.json()


def save_item(item):
    id = item['Id']
    resp = __session__.post(f"{__jf_url__}/Items/{id}", json=item)
    return resp.status_code == 204


@dataclasses.dataclass
class User:
    id: str
    name: str
    raw: dict


def find_user_by_name(name):
    resp = __session__.get(f"{__jf_url__}/Users")
    if resp:
        data = resp.json()
        found = next((u for u in data if u['Name'] == name), None)
        if found:
            allowed_fields = {field.name for field in User.__dataclass_fields__.values()}
            data = {k.lower(): v for k, v in found.items() if k.lower() in allowed_fields}
            data['raw'] = found
            return User(**data)
        else:
            logger.warning(f"Cannot find user '{name}'")


def add_media_ids_to_playlist(pl_id, media_ids, user_id):
    n = 0
    for ids in chunked(media_ids, 10):
        try:
            params = {
                'userId': user_id,
                'ids': ','.join(ids)
            }
            response = __session__.post(f"{__jf_url__}/playlists/{pl_id}/Items", params=params)
            response.raise_for_status()
            n += len(ids)
        except:
            logger.exception(f"Could not add media_ids ({','.join(ids)}) into playlist ({pl_id})")
    return n


def create_playlist(ytm_pl_name, user_id, type=None):
    # http: // {{jf_hostport}} / playlists /?name = test & userId = 85e1d3cd5c8b49de9c225d5f8d39e79e & mediaType = Audio
    params = {
        'name': ytm_pl_name,
        'userId': user_id,
        'mediaType': type
    }
    resp = __session__.post(f"{__jf_url__}/Playlists/", params=params)
    resp.raise_for_status()
    return resp.json()['Id']
