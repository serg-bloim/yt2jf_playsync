import json
import unittest

from ytmusicapi import YTMusic


class MyYTTestCase(unittest.TestCase):
    def test_something(self):
        ytmusic = YTMusic()
        video_id = 'tAGnKpE4NCI'
        # video_id = 'bY3vXr7fm8k'
        song = ytmusic.get_song(video_id)
        print(song)
        pass

    def test_load_playlist(self):
        ytmusic = YTMusic()
        playlist = ytmusic.get_playlist('PL8xOIxSY5muAN86F9a80SOtkHTuKWuC-y')
        print(json.dumps(playlist))
        pass

    def test_search(self):
        ytmusic = YTMusic()
        video_id = 'tAGnKpE4NCI'
        # video_id = 'bY3vXr7fm8k'
        query = "Nothing Else Matters"
        songs = ytmusic.search(query, 'songs')
        vids = ytmusic.search(query, 'videos')
        pass

if __name__ == '__main__':
    unittest.main()
