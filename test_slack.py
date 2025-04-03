import traceback
import unittest
from threading import Event

import requests
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest

from utils import slack
from utils.logs import create_logger

logger = create_logger("main")


class MyTestCase(unittest.TestCase):
    def test_slack_bot(self):
        def handler(action, req:SocketModeRequest, client: SocketModeClient):
            pl = {
                'delete_original': 'true'
            }
            try:
                resp = requests.post(req.payload['response_url'], json=pl)
                resp.raise_for_status()
            except:
                traceback.print_exc()
                pass
            pass
        slack.add_slack_interactive_message_handler("video_replacement", handler)
        Event().wait()

    def test_slack_delete_msg(self):
        ts = '1743596376.000500'
        channel = {'id': 'C02JQJFNWEL', 'name': 'test'}
        slack.__web_client__.chat_delete(channel=channel['id'], ts=ts)


if __name__ == '__main__':
    unittest.main()
