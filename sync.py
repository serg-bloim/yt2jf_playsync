import itertools
import json
import os
import random
import re
from dataclasses import replace
from typing import List

from slack_sdk.socket_mode.request import SocketModeRequest
from ytmusicapi import YTMusic

from utils import slack
from utils.common import get_nested_value, first, format_scaled_number
from utils.db import load_media_mappings, load_settings, load_playlist_configs, save_playlist_config, load_local_media, \
    add_local_media, load_yt_automated_playbooks, load_yt_media_metadata, YtMediaMetadata, save_yt_media_metadata, load_guser_by_id, create_yt_media_metadata
from utils.jf import load_all_items, find_user_by_name, load_item_by_id, save_item, load_jf_playlist, \
    add_media_ids_to_playlist, create_playlist, get_jf_base_url
from utils.logs import create_logger
from utils.slack import add_slack_interactive_message_handler, add_slack_shortcut_handler, send_ephemeral
from utils.ytm import load_flat_playlist, createYtMusic, refresh_access_token, Category

NO_IMAGE_AVAILABLE_URL = 'https://upload.wikimedia.org/wikipedia/commons/thumb/a/ac/No_image_available.svg/300px-No_image_available.svg.png'

SLACK_CHANNEL_DEFAULT = '#playsync'
SLACK_CHANNEL_INFO = os.getenv('SLACK_CHANNEL_PLAYSYNC_INFO', SLACK_CHANNEL_DEFAULT)
SLACK_CHANNEL_MISMATCHED_MEDIA = os.getenv('SLACK_CHANNEL_PLAYSYNC_MISMATCH_MEDIA', SLACK_CHANNEL_DEFAULT)
SLACK_CHANNEL_V2S_LOG = os.getenv('SLACK_CHANNEL_PLAYSYNC_V2S_LOGGING', '#v2s_logging')


def parse_yt_id(path, regex=load_settings().jf_extract_ytid_regex):
    m = re.search(regex, path)
    if m:
        return m.group()


def process_media_metadata_mismatch(req, action):
    logger = create_logger("yt_meta_mismatch_fix")
    payload = json.loads(action['value'])
    yt_id = payload['yt_id']
    jf_id = payload['jf_id']
    uid = payload['uid']
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


def process_media_metadata_sync(req, action):
    sync_all_playlists()


def process_video_replacement(req: SocketModeRequest, action):
    logger = create_logger("yt_auto.v2s")
    data = json.loads(action['selected_option']['value'])
    sid = data['sid']
    vid = data['vid']
    if sid and vid:
        if mm := first(load_yt_media_metadata(yt_id=vid)):
            mm.alt_id = sid
            save_yt_media_metadata(mm)
            logger.info(f"Associated video {mm.yt_id} {mm.title} by {mm.artist} with media {mm.alt_id}")
            try:
                slack.delete_current_message(req)
            except:
                logger.exception(f"Failed to delete video resolution message for vid: {vid} sid: {sid}")
            try:
                slack.send_message(f"Video {vid} got a replacement song {sid}", SLACK_CHANNEL_V2S_LOG)
            except:
                logger.exception(f"Failed to slack log video replacement: {vid} --> {sid}")
    pass


def process_video_scan(req: SocketModeRequest):
    sub_videos_with_songs()


def process_init_video_resolve(req: SocketModeRequest, action=None):
    logger = create_logger("yt_auto.v2s")
    metadata = load_yt_media_metadata(alt_id=None, category='video')
    uid = req.payload['user']['id']
    try:
        slack.delete_current_message(req)
    except:
        logger.exception(f"Failed to delete a reload message")
    if metadata:
        vids = [mm.yt_id for mm in metadata]
        resolve_video_substitution(vids, uid)
    else:
        send_ephemeral("There are no videos for replacement", SLACK_CHANNEL_DEFAULT, uid)


add_slack_interactive_message_handler("media_metadata_mismatch", process_media_metadata_mismatch)
add_slack_interactive_message_handler("sync_playlists", process_media_metadata_sync)
add_slack_interactive_message_handler("video_replacement", process_video_replacement)
add_slack_interactive_message_handler("v2s_resolve_more_videos", process_init_video_resolve)
add_slack_shortcut_handler("vsd-init-scan", process_video_scan)
add_slack_shortcut_handler("vsd-resolve-videos", process_init_video_resolve)


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
    pl_additions = {}
    pl_misses = {}
    for pl_cfg in pl_configs:
        try:
            if pl_cfg.sync:
                added_into_playlist, not_found = sync_playlist(pl_cfg, user=user, items=jf_items, logger=logger)
                pl_additions[pl_cfg.jf_pl_id] = added_into_playlist
                pl_misses[pl_cfg.jf_pl_id] = not_found
            else:
                logger.debug(f"Playlist '{pl_cfg.ytm_pl_name}/{pl_cfg.ytm_pl_id}' has flag SYNC=OFF. Ignoring the playlist.")
        except:
            logger.exception(f"Error happened while syncing YT playlist '{pl_cfg.ytm_pl_name}'[{pl_cfg.ytm_pl_id}] with JF playlist '{pl_cfg.jf_pl_name}'/[{pl_cfg.jf_pl_id}]")

    local_media = load_local_media()
    local_media_ids = {m.jf_id for m in local_media}
    new_items = [itm for itm in jf_items if itm['Id'] not in local_media_ids]
    add_local_media(new_items)
    pl_lookup = {pl.jf_pl_id: pl for pl in pl_configs}
    if new_items:
        msg = "New items:"
        for pl_id, new_ids in pl_additions.items():
            if new_ids:
                pl_cfg = pl_lookup[pl_id]
                msg += f"\n{pl_cfg.jf_pl_name} got {len(new_ids)} new media"
        playlist_new_media = {id for pl_ids in pl_additions.values() for id in pl_ids}
        no_playlist_new_media = [m for m in new_items if m['Id'] not in playlist_new_media]
        if no_playlist_new_media:
            msg += f"\n{len(no_playlist_new_media)} new media in Library"
        slack.send_message(msg, SLACK_CHANNEL_DEFAULT)


def select_yt_thumbnail(yt_media):
    thumbnails = yt_media.get('thumbnails') or []

    def order(th):
        return th.get('preference') or 100

    best = min(thumbnails, key=order, default={'url': ''})
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
                    "action_id": "media_metadata_mismatch",
                    "value": json.dumps({
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
                    "action_id": "sync_playlists",
                    "style": "danger",
                    "value": json.dumps({
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
            logger.info(f"Queueing media '{jf_item['Name']}'[{yt_song['url']}] into JF playlist '{pl_config.jf_pl_name}'")
        else:
            if yt_id in recovered_items:
                recovered = recovered_items[yt_id]
                if recovered['Name'] == yt_song['title'] and yt_song['channel'] in recovered['Artists']:
                    jf_item_full = load_item_by_id(recovered['Id'], user.id)
                    jf_item_full['ProviderIds']['YT'] = yt_id
                    if save_item(jf_item_full):
                        already_in_library.append(recovered['Id'])
                        logger.info(f"Recovered YT media {yt_song['title']} / {yt_song['channel']} from local media {recovered['Name']} / {recovered['Artists']}")
                    else:
                        logger.warning(f"Cannot save yt_id{yt_id}({yt_song['channel']}/{yt_song['title']}) for local media '{recovered['Name']} / {recovered['Artists']} ({recovered['Id']})'")
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
    msg1 = f"Added {added_n} out of {len(already_in_library)} possible medias into the playlist {pl_config.jf_pl_name}"
    msg2 = f"{len(not_in_lib)} medias are not in the library"

    # Send out a report about medias that were not possible to recover automatically
    for batch in itertools.batched(recovery_media_mismatch[:2], 15):
        send_mismatch_report(batch, user, SLACK_CHANNEL_MISMATCHED_MEDIA)

    log_level_func(msg1)
    if not_in_lib:
        logger.warning(msg2)

    return already_in_library, not_in_lib


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


def format_vid_replacement_message(video_meta: YtMediaMetadata, song_candidates_meta: list[YtMediaMetadata]):
    def format_duration(dur_sec: int):
        min = dur_sec // 60
        sec = dur_sec % 60
        return f"{min}:{sec:02}"

    blocks = []
    video_url = f"https://music.youtube.com/watch?v={video_meta.yt_id}"
    artists = video_meta.artist
    blocks.append({
        "type": "section",
        "fields": [
            {
                "type": "mrkdwn",
                "text": f"""*VIDEO to replace*
<{video_url}|{video_meta.title}> ({format_duration(video_meta.duration)})
<{video_url}|by {artists}>"""
            },
        ],
        "accessory": {
            "type": "image",
            "image_url": video_meta.thumbnail_url or NO_IMAGE_AVAILABLE_URL,
            "alt_text": "yt thumbnail"
        }
    })
    options = []
    for i, s in enumerate(song_candidates_meta, start=1):
        artists = s.artist
        sid = s.yt_id
        song_url = f"https://music.youtube.com/watch?v={sid}"
        short_title = s.title[:20]
        short_artists = artists[:20]
        options.append((sid, f"{i}. {short_title} ({format_duration(s.duration)})\nby {short_artists} ({s.views_cnt})"))
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"""{i}. <{song_url}|{s.title}> ({format_duration(s.duration)})
     <{song_url}|{s.album_name}> {s.views_cnt}
     <{song_url}|by {artists}>"""
            },
            "accessory": {
                "type": "image",
                "image_url": s.thumbnail_url or NO_IMAGE_AVAILABLE_URL,
                "alt_text": "yt thumbnail"
            }
        })
        # print(f"Candidate: {s['title']} - {artists} ({views} views) https://music.youtube.com/watch?v={sid}  Thumbnail: {pick_thumbnail(s['thumbnails'])}")

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "Select a replacement"
        },
        "accessory": {
            "type": "overflow",
            "options": [{
                "text": {
                    "type": "plain_text",
                    "text": opt
                },
                "value": json.dumps({
                    'vid': video_meta.yt_id,
                    'sid': sid
                })
            } for sid, opt in options],
            "action_id": f"video_replacement"
        }
    })
    return blocks


def extract_meta(song_search_rec):
    return YtMediaMetadata(id='',
                           yt_id=song_search_rec['videoId'],
                           title=song_search_rec['title'],
                           artist=', '.join(a['name'] for a in song_search_rec['artists']),
                           category=song_search_rec['resultType'],
                           album_name=song_search_rec['album']['name'],
                           duration=song_search_rec['duration_seconds'],
                           views_cnt=song_search_rec.get('views'),
                           thumbnail_url=max(song_search_rec['thumbnails'], key=lambda thn: thn['height'], default={'url': ''})['url'])


def format_resolve_video_load_more(more_vids_n):
    return [
        {
            'type': 'section',
            "text": {
                "type": "mrkdwn",
                "text": f"There are {more_vids_n} more videos to replace"},
            "accessory": {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Load more videos to resolve"
                },
                "style": "primary",
                "value": "123",
                "action_id": f"v2s_resolve_more_videos"}
        }
    ]


def resolve_video_substitution(vid_sub_candidates: List[str], slack_user_recipient):
    ytm = YTMusic()
    logger = create_logger("yt_auto.v2s")
    metadata: dict[str, YtMediaMetadata] = {mm.yt_id: mm for mm in load_yt_media_metadata(alt_id=None)}
    candidates_meta = [metadata[v] for v in vid_sub_candidates if v in metadata]
    if diff := len(vid_sub_candidates) - len(candidates_meta) > 0:
        logger.warning(f"{diff} medias are not in db/metadata")
    if candidates_meta:
        sample_size = min(len(candidates_meta), int(os.getenv("V2S_SAMPLE_SIZE", default='5')))
        logger.info(f"Resolving {sample_size} videos out of {len(candidates_meta)}")
        sample: list[YtMediaMetadata] = random.sample(candidates_meta, sample_size)
        for vm in sample:
            query = f"{vm.title} {vm.artist}"
            logger.debug(f"Searching for [{query}] videoId='{vm.yt_id}'")
            songs = ytm.search(query, 'songs')
            if songs:
                top5res = [extract_meta(s) for s in songs[:5]]
                for s in top5res:
                    song = ytm.get_song(s.yt_id)
                    s.views_cnt = format_scaled_number(int(get_nested_value(song, 'videoDetails', 'viewCount') or '0')) + f" / {s.views_cnt}"
                slack.send_ephemeral(f"Videos for resolution", SLACK_CHANNEL_DEFAULT, slack_user_recipient, blocks=format_vid_replacement_message(vm, top5res))
        if (more_vids := len(vid_sub_candidates) - sample_size) > 0:
            slack.send_ephemeral(f"Load more videos to resolve", SLACK_CHANNEL_DEFAULT, slack_user_recipient, blocks=format_resolve_video_load_more(more_vids))
        pass


def sub_videos_with_songs():
    logger = create_logger("yt_auto.v2s")
    guser_id = os.getenv('GOOGLE_USER_ID')
    usr = load_guser_by_id(guser_id)
    pl_cfgs = [pl for pl in load_yt_automated_playbooks() if pl.yt_user == usr.yt_user_id and (pl.vsd_replace_in_src or pl.vsd_replace_during_copy or pl.copy)]
    yt_media_metadata = {mm.yt_id: mm for mm in load_yt_media_metadata()}
    if pl_cfgs:
        if usr.is_refresh_token_valid():
            if not usr.is_access_token_valid():
                # Replace with a token refresh
                refresh_access_token(usr)

            ytc = createYtMusic(usr.access_token, usr.refresh_token)
            user_playlists = {}
            new_metadata = []
            unresolved_videos = []
            for pl in pl_cfgs:
                playlist = ytc.get_playlist(pl.yt_pl_id, limit=None)
                user_playlists[playlist['id']] = playlist
                replaceable = {}
                pl_ids_to_media = {t['videoId']: t for t in playlist['tracks']}
                for media in playlist['tracks']:
                    mid = media['videoId']
                    if mid not in yt_media_metadata:
                        new_metadata.append(media)
                    category = Category.SONG if media['videoType'] == 'MUSIC_VIDEO_TYPE_ATV' else Category.VIDEO
                    media['category'] = category
                    if category == Category.VIDEO:
                        if (meta := yt_media_metadata.get(mid)) and meta.alt_id:
                            replaceable[mid] = meta.alt_id
                        else:
                            unresolved_videos.append((media, pl, playlist))
                if pl.vsd_replace_in_src:
                    songs_to_add = [mid for mid in replaceable.values() if mid not in pl_ids_to_media]
                    logger.info(f"Adding {len(songs_to_add)} replacement medias into '{playlist['title']}': {songs_to_add}")
                    if songs_to_add:
                        ytc.add_playlist_items(pl.yt_pl_id, songs_to_add)
                    videos_to_remove = [pl_ids_to_media[mid] for mid in replaceable.keys()]
                    logger.info(f"Removing {len(videos_to_remove)} videos from '{playlist['title']}': [{','.join(replaceable.keys())}]")
                    if videos_to_remove:
                        ytc.remove_playlist_items(pl.yt_pl_id, videos_to_remove)
                if pl.copy:
                    dst_playlist = ytc.get_playlist(pl.copy_dst, limit=None)
                    dst_media_ids = {t for t in dst_playlist['tracks']}
                    media_to_copy = set(pl_ids_to_media.keys()) - dst_media_ids
                    if pl.vsd_replace_during_copy:
                        songs_to_copy = {mid for mid in media_to_copy if pl_ids_to_media[mid]['category'] == Category.SONG}
                        media_to_copy = [mid if is_song else replaceable[mid] for mid in media_to_copy if (is_song := mid in songs_to_copy) or mid in replaceable]
                    new_media_to_copy = media_to_copy - dst_media_ids
                    logger.info(f"Copying {len(new_media_to_copy)} medias into '{playlist['title']}': {new_media_to_copy}")
                    ytc.add_playlist_items(pl.copy_dst, new_media_to_copy)
                pass

            # Select medias that are not in the metadata yet
            logger.info(f"Found {len(new_metadata)} new medias in user's ({usr.yt_user_id}) playlists")
            for media in new_metadata:
                mm = None
                try:
                    artists = ', '.join(a['name'] for a in media['artists'])
                    mm = YtMediaMetadata(
                        id=None,
                        yt_id=media['videoId'],
                        title=media['title'],
                        artist=artists,
                        category=str(media['category']),
                        album_name=media['album'],
                        duration=media['duration_seconds'],
                        views_cnt=media['views'],
                        thumbnail_url=max(media['thumbnails'], key=lambda thn: thn['height'],
                                          default={'url': 'https://upload.wikimedia.org/wikipedia/commons/thumb/a/ac/No_image_available.svg/300px-No_image_available.svg.png'})['url']
                    )
                    create_yt_media_metadata(mm)
                except:
                    logger.exception(f"Failed to save {mm}")
            if unresolved_videos:
                resolve_video_substitution([v['videoId'] for v, pl_cfg, pl_data in unresolved_videos], usr.slack_user)
