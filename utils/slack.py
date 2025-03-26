import os
from collections import defaultdict

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse

__slack_bot_token__ = os.getenv('SLACK_TOKEN_XOXB')
__slack_app_token__ = os.getenv('SLACK_TOKEN_XAPP')
__web_client__ = WebClient(token=__slack_bot_token__)

__message_handlers__ = defaultdict(list)
__shortcut_handlers__ = defaultdict(list)

from utils.logs import create_logger


def add_slack_interactive_message_handler(type, handler):
    __message_handlers__[type].append(handler)


def add_slack_shortcut_handler(callback_id, handler):
    __shortcut_handlers__[callback_id].append(handler)


def __setup_slack_callback__():
    __socket_client__ = SocketModeClient(
        # This app-level token will be used only for establishing a connection
        app_token=__slack_app_token__,  # xapp-A111-222-xyz
        # You will be using this WebClient for performing Web API calls in listeners
        web_client=__web_client__  # xoxb-111-222-xyz
    )

    def process(client: SocketModeClient, req: SocketModeRequest):
        logger = create_logger('slack')
        if req.type == 'interactive':
            if req.payload['type'] == 'shortcut':
                try:
                    sh_id = req.payload['callback_id']
                    handlers = __shortcut_handlers__.get(sh_id, [])
                    for hdl in handlers:
                        try:
                            hdl(req)
                        except:
                            logger.exception("Error during shortcut handler")
                except:
                    logger.exception("Cannot get shortcut details")
            elif req.payload['type'] == 'block_actions':
                for action in req.payload['actions']:
                    try:
                        type = action['action_id']
                        handlers = __message_handlers__.get(type, [])
                        for hdl in handlers:
                            try:
                                hdl(action, req)
                            except:
                                logger.exception("Error during action handler")
                    except:
                        logger.exception("Cannot get action details")
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


def send_ephemeral(msg, channel_id, user_id, blocks=None):
    try:
        response = __web_client__.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text=msg,
            blocks=blocks
        )
        print(f"Message sent")
    except SlackApiError as e:
        print(f"Error sending message: {e.response['error']}")
