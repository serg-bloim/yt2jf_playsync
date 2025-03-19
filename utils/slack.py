import json
import os
from collections import defaultdict
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.socket_mode.request import SocketModeRequest

__slack_bot_token__ = os.getenv('SLACK_TOKEN_XOXB')
__slack_app_token__ = os.getenv('SLACK_TOKEN_XAPP')
__web_client__ = WebClient(token=__slack_bot_token__)

__message_handlers__ = defaultdict(list)


def add_slack_interactive_message_handler(type, handler):
    __message_handlers__[type].append(handler)


def __setup_slack_callback__():
    __socket_client__ = SocketModeClient(
        # This app-level token will be used only for establishing a connection
        app_token=__slack_app_token__,  # xapp-A111-222-xyz
        # You will be using this WebClient for performing Web API calls in listeners
        web_client=__web_client__  # xoxb-111-222-xyz
    )

    def process(client: SocketModeClient, req: SocketModeRequest):
        if req.type == 'interactive':
            if req.payload['type'] == 'block_actions':
                for action in req.payload['actions']:
                    try:
                        val_str = action['value']
                        val = json.loads(val_str)
                        type = val.get('type')
                        handlers = __message_handlers__.get(type, [])
                        for hdl in handlers:
                            try:
                                hdl(val, req)
                            except:
                                pass
                    except:
                        pass
        response = SocketModeResponse(envelope_id=req.envelope_id)
        client.send_socket_mode_response(response)

    __socket_client__.socket_mode_request_listeners.append(process)
    __socket_client__.connect()


__setup_slack_callback__()


def send_message(msg, channel_id, blocks=None):
    try:
        response = __web_client__.chat_postMessage(
            channel=channel_id,
            text=msg,
            blocks=blocks
        )
        print(f"Message sent: {response['message']['text']}")
    except SlackApiError as e:
        print(f"Error sending message: {e.response['error']}")
