import yt_dlp


def load_flat_playlist(playlist_id, load_entries=True):
    URL = f'https://music.youtube.com/playlist?list={playlist_id}'
    ydl_opts = {'extract_flat': True}

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(URL, download=False, process=load_entries)
        # ℹ️ ydl.sanitize_info makes the info json-serializable
        return ydl.sanitize_info(info)
    pass
