import traceback
import urllib
from datetime import timezone, timedelta, datetime
from http.server import SimpleHTTPRequestHandler, HTTPServer
from ssl import SSLContext
from urllib.parse import urlparse
from pyyoutube import Client, Api

from utils.common import first, root_dir


def run_auth_server(client: Client):
    token_resp = None
    class MyHandler(SimpleHTTPRequestHandler):
        def do_GET(self):
            nonlocal token_resp
            try:
                redirect_uri = 'https://localhost:1234'
                response_url = redirect_uri + self.path
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                token = client.generate_access_token(authorization_response=response_url, redirect_uri=redirect_uri + '/abc', state=first(qs['state']))
                token_resp = token
                try:
                    api = Api(client_id=client.client_id, client_secret=client.client_secret, access_token=client.access_token)
                    profile = api.get_profile(client.access_token)
                except:
                    pass
                EDT = timezone(timedelta(hours=-4))
                expires = datetime.fromtimestamp(token.expires_at, tz=EDT)
                print(f"Token expires at {expires}")
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(f"""<html><body><h1>Authenticated!</h1>
                                    <table>
                                    <tr>
                                    <td>Access token</td>
                                    <td>{token.access_token}</td>
                                    </tr><tr>
                                    <td>Refresh token</td>
                                    <td>{token.refresh_token}</td>
                                    </tr><tr>
                                    <td>Expires in</td>
                                    <td>{token.expires_in}</td>
                                    </tr><tr>
                                    <td>Expires at</td>
                                    <td>{expires} ({token.expires_at})</td>
                                    </tr>
                                    </table>""".encode())

                print("Shutdown")
                import threading
                assassin = threading.Thread(target=self.server.shutdown)
                assassin.daemon = True
                assassin.start()
                print("Shutdown")
            except:
                traceback.print_exc()

    PORT = 1234
    server_address = ("0.0.0.0", PORT)
    httpd = HTTPServer(server_address, MyHandler)
    ssl_context = SSLContext()
    ssl_context.load_cert_chain(root_dir() /'test/cert/cert.pem', root_dir() / 'test/cert/key.pem')
    httpd.socket = ssl_context.wrap_socket(httpd.socket, server_side=True)
    httpd.serve_forever()
    pass
    return token_resp