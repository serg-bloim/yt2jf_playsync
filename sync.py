import itertools
import json
import os
import re
from dataclasses import replace
from utils import slack
from utils.common import get_nested_value
from utils.db import load_media_mappings, load_settings, load_playlist_configs, save_playlist_config
from utils.jf import load_all_items, find_user_by_name, load_item_by_id, save_item, load_jf_playlist, \
    add_media_ids_to_playlist, create_playlist, get_jf_base_url
from utils.logs import create_logger
from utils.slack import add_slack_interactive_message_handler
from utils.ytm import load_flat_playlist

SLACK_CHANNEL_DEFAULT = '#playsync'
SLACK_CHANNEL_INFO = os.getenv('SLACK_CHANNEL_PLAYSYNC_INFO', SLACK_CHANNEL_DEFAULT)
SLACK_CHANNEL_MISMATCHED_MEDIA = os.getenv('SLACK_CHANNEL_PLAYSYNC_MISMATCH_MEDIA', SLACK_CHANNEL_DEFAULT)


def parse_yt_id(path, regex=load_settings().jf_extract_ytid_regex):
    m = re.search(regex, path)
    if m:
        return m.group()

def process_media_metadata_mismatch(payload, req):
    logger = create_logger("yt_meta_mismatch_fix")
    yt_id=payload['yt_id']
    jf_id=payload['jf_id']
    uid=payload['uid']
    jf_item_full = load_item_by_id(jf_id, uid)
    old_yt_id = get_nested_value(jf_item_full, 'ProviderIds', 'YT')
    if old_yt_id is None:
        jf_item_full['ProviderIds']['YT'] = yt_id
        save_item(jf_item_full)
    elif old_yt_id == yt_id:
        pass
    else:
        logger.warning(f"Cannot set YT_ID=[{yt_id}] for media {jf_item_full['title']} / {jf_id}, cause it already has YT_ID=[{old_yt_id}] ")

    pass

def process_media_metadata_sync(payload, req):
    sync_all_playlists()

add_slack_interactive_message_handler("media_metadata_mismatch", process_media_metadata_mismatch)
add_slack_interactive_message_handler("sync_playlists", process_media_metadata_sync)

def update_yt_ids_in_db():
    logger = create_logger("yt_ids_sync")
    mappings = load_media_mappings()
    jf_items = load_all_items("Audio", "Path,ProviderIds")
    settings = load_settings()
    user = find_user_by_name(settings.jf_user_name)
    successful = []
    already_done = []
    failed = []
    for m in mappings:
        try:
            jf_path = re.sub(settings.pf2jf_path_conv_search, settings.pf2jf_path_conv_replace, m.local_path)
            jf_item = next((i for i in jf_items if i['Path'] == jf_path), None)
            if jf_item:
                jf_id = jf_item['Id']
                jf_name = jf_item['Name']
                yt_provider_id = jf_item['ProviderIds'].get('YT')
                if yt_provider_id is None:
                    jf_item_full = load_item_by_id(jf_id, user.id)
                    jf_item_full['ProviderIds']['YT'] = m.yt_id
                    if save_item(jf_item_full):
                        logger.info(f"Media '{jf_name}'({jf_id}) got updated with YT id {m.yt_id}")
                        successful.append(jf_item)
                        # delete_mapping(m)
                    else:
                        logger.error(f"Failed to update media '{jf_name}'({jf_id}) with YT id {m.yt_id}")
                        failed.append(jf_item)
                else:
                    logger.info(f"Media '{jf_name}'({jf_id}) already has YT id {yt_provider_id}")
                    already_done.append(jf_item)
            else:
                logger.warn(f"Cannot find JellyFin Item for path [{jf_path}]")
                failed.append({'Id': None, 'Name': None, 'Path': jf_path})
        except:
            logger.exception(f"Failed to process mapping {m}")
            failed.append({'Id': None, 'Name': None, 'Path': m.local_path})

    log_level_function = logger.info if len(failed) == 0 else logger.warning
    log_level_function(f"""Processed: {len(mappings)}.
Successfully updated items: {len(successful)}.
Already contained yt_id: {len(already_done)}.
Failed: {len(failed)}.""")


def sync_all_playlists():
    logger = create_logger("pl_sync")
    pl_configs = load_playlist_configs()
    jf_items = load_all_items("Audio", "Path,ProviderIds")
    settings = load_settings()
    user = find_user_by_name(settings.jf_user_name)

    for pl_cfg in pl_configs:
        try:
            if pl_cfg.sync:
                sync_playlist(pl_cfg, user=user, items=jf_items, logger=logger)
            else:
                logger.debug(
                    f"Playlist '{pl_cfg.ytm_pl_name}/{pl_cfg.ytm_pl_id}' has flag SYNC=OFF. Ignoring the playlist.")
        except:
            logger.exception(
                f"Error happened while syncing YT playlist '{pl_cfg.ytm_pl_name}'[{pl_cfg.ytm_pl_id}] with JF playlist '{pl_cfg.jf_pl_name}'/[{pl_cfg.jf_pl_id}]")


def select_yt_thumbnail(yt_media):
    thumbnails = yt_media.get('thumbnails') or []
    def order(th):
        return th.get('preference') or 100

    best = min(thumbnails, key=order, default={'url':''})
    return best.get('url')


def format_metadata_mismatch_report(yt, jf, user):
    return [
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"{yt['channel']}\n<{yt['url']}|{yt['title']}>"
                },
            ],
            "accessory": {
                "type": "image",
                "image_url": select_yt_thumbnail(yt),
                "alt_text": "yt thumbnail"
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"{' '.join(jf['Artists'])}\n<{get_jf_base_url()}/web/#/details?id={jf['Id']}&serverId={jf['ServerId']}|{jf['Name']}>"
                },
            ],
            "accessory": {
                "type": "image",
                "image_url": f"{get_jf_base_url()}/Items/{jf['Id']}/Images/Primary",
                "alt_text": "jf thumbnail"
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "emoji": True,
                        "text": "Approve"
                    },
                    "style": "primary",
                    "value": json.dumps({
                                          "type": "media_metadata_mismatch",
                                          "action": "confirm",
                                          "yt_id": yt['id'],
                                          "jf_id": jf['Id'],
                                          "uid": user.id,
                                        })
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "emoji": True,
                        "text": "Sync"
                    },
                    "style": "danger",
                    "value":  json.dumps({
                                          "type": "sync_playlists",
                                        })
                }
            ]
        }
    ]


def send_mismatch_report(mismatched_media, user, channel_id):
    report = []
    for (yt, jf) in mismatched_media:
        report += format_metadata_mismatch_report(yt, jf, user)
        report.append({"type": "divider"})
    slack.send_message("Media mismatch report", channel_id, blocks=report)


def sync_playlist(pl_config, user=None, items=None, logger=None):
    logger = logger or create_logger("pl_sync")
    itms = items or load_all_items("Audio", "Path,ProviderIds")
    ytm2items = {itm['ProviderIds']['YT']: itm for itm in itms if 'YT' in itm['ProviderIds']}
    recovered_items = {parse_yt_id(itm['Path']): itm for itm in itms if 'YT' not in itm['ProviderIds']}
    user = user or find_user_by_name(load_settings().jf_user_name)
    yt_playlist_songs = load_flat_playlist(pl_config.ytm_pl_id)
    jf_playlist_songs = load_jf_playlist(pl_config.jf_pl_id, user.id, "ProviderIds")
    jf_playlist_yt_ids = {e['ProviderIds']['YT'] for e in jf_playlist_songs['Items']}
    already_in_library = []
    recovery_media_mismatch = []
    not_in_lib = []
    for yt_song in yt_playlist_songs['entries']:
        yt_id = yt_song['id']
        if yt_id in jf_playlist_yt_ids:
            # This song is already in the JF playlist
            continue
        jf_item = ytm2items.get(yt_id)
        if jf_item:
            already_in_library.append(jf_item['Id'])
            logger.info(
                f"Queueing media '{jf_item['Name']}'[{yt_song['url']}] into JF playlist '{pl_config.jf_pl_name}'")
        else:
            if yt_id in recovered_items:
                recovered = recovered_items[yt_id]
                if recovered['Name'] == yt_song['title'] and yt_song['channel'] in recovered['Artists']:
                    jf_item_full = load_item_by_id(recovered['Id'], user.id)
                    jf_item_full['ProviderIds']['YT'] = yt_id
                    if save_item(jf_item_full):
                        already_in_library.append(recovered['Id'])
                        logger.info(
                            f"Recovered YT media {yt_song['title']} / {yt_song['channel']} from local media {recovered['Name']} / {recovered['Artists']}")
                    else:
                        logger.warning(
                            f"Cannot save yt_id{yt_id}({yt_song['channel']}/{yt_song['title']}) for local media '{recovered['Name']} / {recovered['Artists']} ({recovered['Id']})'")
                else:
                    not_in_lib.append(yt_song)
                    recovery_media_mismatch.append((yt_song, recovered))
                    logger.warning(
                        f"Metadata doesn't match for recovery: YT media {yt_song['title']} / {yt_song['channel']}[{yt_id}] and local media {recovered['Name']} / {recovered['Artists']}[{recovered['Id']}]")
            else:
                not_in_lib.append(yt_song)
                logger.warning(f"Cannot find media '{yt_song['channel']}/{yt_song['title']}'[{yt_song['url']}] in local library.")

    added_n = add_media_ids_to_playlist(pl_config.jf_pl_id, already_in_library, user_id=user.id)
    log_level_func = logger.info if added_n == len(already_in_library) else logger.warning
    msg0 = f"Syncing playlist '{pl_config.ytm_pl_name}/{pl_config.jf_pl_name}'"
    msg1 = f"Added {added_n} out of {len(already_in_library)} possible medias into the playlist {pl_config.jf_pl_name}"
    msg2 = f"{len(not_in_lib)} medias are not in the library"
    # slack.send_message('\n'.join([msg0, msg1, msg2]), SLACK_CHANNEL_INFO)

    # Send out a report about medias that were not possible to recover automatically
    for batch in itertools.batched(recovery_media_mismatch[:2], 15):
        send_mismatch_report(batch, user, SLACK_CHANNEL_MISMATCHED_MEDIA)

    log_level_func(msg1)
    if not_in_lib:
        logger.warning(msg2)


def update_pl_cfg_in_db():
    logger = create_logger("pl_upd")
    pl_configs = load_playlist_configs()
    settings = load_settings()
    user = find_user_by_name(settings.jf_user_name)
    jf_playlists = None

    def get_jf_playlists():
        nonlocal jf_playlists
        if not jf_playlists:
            jf_playlists = load_all_items('Playlist')
        return jf_playlists

    for pl_cfg in pl_configs:
        try:
            if pl_cfg.sync:
                old = replace(pl_cfg)

                yt_pl = load_flat_playlist(pl_cfg.ytm_pl_id, load_entries=False)
                pl_cfg.ytm_pl_name = yt_pl['title']

                jf_pl = None
                if pl_cfg.jf_pl_id:
                    try:
                        jf_pl = load_item_by_id(pl_cfg.jf_pl_id, user.id)
                    except:
                        pass
                if jf_pl is None:
                    pl_cfg.jf_pl_id = None
                if pl_cfg.jf_pl_name:
                    playlists = get_jf_playlists()
                    jf_pl = next((pl for pl in playlists if pl['Name'] == pl_cfg.jf_pl_name), None)
                if jf_pl is None:
                    id = create_playlist(pl_cfg.jf_pl_name or pl_cfg.ytm_pl_name, user.id, type="Audio")
                    jf_pl = load_item_by_id(id, user.id)
                if jf_pl:
                    pl_cfg.jf_pl_id = jf_pl['Id']
                    pl_cfg.jf_pl_name = jf_pl['Name']
                else:
                    logger.error(f"Could not find a Playlist({pl_cfg.jf_pl_name})")

                if old != pl_cfg:
                    save_playlist_config(pl_cfg)
                    logger.info(f"Updated PlaylistConfig: {old} -> {pl_cfg}")
        except:
            logger.exception(
                f"Error happened while syncing YT playlist({pl_cfg.ytm_pl_id}) with JF playlist '{pl_cfg.jf_pl_name}'")
