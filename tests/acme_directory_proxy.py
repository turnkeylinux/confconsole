"""Loopback-only CONNECT fixture for installed ACME wizard tests."""

import http.server
from pathlib import Path
import socketserver
import ssl
import time

ROOT = Path('/root/acme-directory-qa')


class Proxy(socketserver.StreamRequestHandler):
    def handle(self):
        request = self.rfile.readline()
        if not request.startswith(b'CONNECT acme-v02.api.letsencrypt.org:443 '):
            return
        while self.rfile.readline().strip():
            pass
        with (ROOT / 'requests.log').open('a') as log:
            log.write('directory request\n')
        self.wfile.write(b'HTTP/1.1 200 Connection established\r\n\r\n')
        self.wfile.flush()
        mode = (ROOT / 'mode').read_text().strip()
        if mode == 'timeout':
            time.sleep(7)
            return
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(ROOT / 'cert.pem', ROOT / 'key.pem')
        try:
            with context.wrap_socket(self.connection, server_side=True) as connection:
                connection.recv(8192)
                status = 503 if mode == 'http-error' else 200
                body = {
                    'invalid-json': b'not JSON',
                    'invalid-meta': b'{"meta":null}',
                }.get(mode, b'{"meta":{"termsOfService":"https://example.org/terms.pdf"}}')
                header = (f'HTTP/1.1 {status} {http.server.BaseHTTPRequestHandler.responses[status][0]}\r\n'
                          f'Content-Length: {len(body)}\r\nConnection: close\r\n\r\n').encode()
                connection.sendall(header + body)
        except (ssl.SSLError, ConnectionError, OSError):
            # Rejection of the untrusted certificate is an expected case.
            pass


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


with Server(('127.0.0.1', 18998), Proxy) as server:
    server.serve_forever()
