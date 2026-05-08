import unittest

from ytmusicapi import YTMusic

from test.config import Config
from utils.ytm import createYtMusic


class MyTestCase(unittest.TestCase):
    def test_read_playlist(self):
        ytc = createYtMusic(Config.google_token.access_token, Config.google_token.refresh_token)
        pl_src_id = Config.Playlists.yt_src_id
        ytc.get_playlist(pl_src_id)
        pass

    def test_noauth_seqrch(self):
        from ytmusicapi import YTMusic

        yt = YTMusic('oauth.json')
        # playlistId = yt.create_playlist('test', 'test description')
        search_results = yt.search('Oasis Wonderwall')
        # yt.add_playlist_items(playlistId, [search_results[0]['videoId']])
        pass


if __name__ == '__main__':
    unittest.main()
