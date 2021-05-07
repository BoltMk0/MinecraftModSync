from serversync.common import *
from socket import socket, AF_INET, SOCK_STREAM, timeout, error
from os import remove
from time import sleep
import requests
import atexit


_currently_downloading = None


def _cleanup():
    global _currently_downloading
    if _currently_downloading is not None:
        remove(_currently_downloading)
        print('[OK] Removed partial downloaded file: {}'.format(_currently_downloading))


atexit.register(_cleanup)


class Client:
    def __init__(self, sock_timeout=5):
        self._sock_timeout = sock_timeout
        self.conf = ServerSyncConfig()
        self.on_progress_cb = None
        self.sock = None

        self._currently_downloading = None  # When None, not downloading, else the filepath

    def connect(self, ip=None, port=None):
        if self.sock is not None:
            self.close()

        if ip is None:
            ip = self.conf.server_ip
        if port is None:
            port = self.conf.server_port

        self.sock = self._make_sock()
        try:
            # This step will both ping the server to check connection and inform server of the client version (required)
            if self.get_server_ver() == 'legacy':
                raise UnsupportedServerError('This client version does not support legacy servers. Either downgrade '
                                             'serversync to legacy (0.x) version, or contact your server administrator.')

            # Inform server whether or not this client allows redirects
            msg = PingMessage()
            msg[PingMessage.KEY_SUPPORTS_HTTP_REDIRECT] = self.conf.allow_redirects
            self.send(msg)

        except:
            self.sock.close()
            raise

    def close(self):
        if self.sock is not None:
            self.sock.close()
            self.sock = None

    def _make_sock(self):
        sock = socket(AF_INET, SOCK_STREAM)
        sock.settimeout(self._sock_timeout)
        sock.connect(self.conf.server_address)
        return sock

    def get_server_ver(self):
        try:
            ret = self.send(PingMessage())
            if ret.type == PingMessage.TYPE_STR:
                return ret[PingMessage.KEY_VERSION]
            else:
                raise ValueError('Unexpected server response: {}'.format(ret))
        except json.JSONDecodeError:
            # Could be legacy server
            ret_bytes = self.send_raw(b'ping')
            if ret_bytes == b'pong':
                return 'legacy'
            else:
                raise ValueError('Unknown server')

    def send(self, message: Message):
        return Message.decode(self.send_raw(message.encode()))

    def send_raw(self, data: bytes):
        if self.sock is None:
            self.connect()

        to_write = len(data)
        while to_write > 0:
            if to_write > DOWNLOAD_BUFFER_SIZE:
                nbytes = self.sock.send(data[-to_write:DOWNLOAD_BUFFER_SIZE-to_write])
            else:
                nbytes = self.sock.send(data[-to_write:])
            to_write -= nbytes

        ret = b''
        buf = bytearray(DOWNLOAD_BUFFER_SIZE)
        retry_counter = 0
        while True:
            nbytes = self.sock.recv_into(buf)
            if nbytes == 0:
                # All messages are terminated with a null byte.
                if ret.endswith(bytes(1)):
                    break
                else:
                    if retry_counter == 10*self._sock_timeout:
                        break
                    retry_counter += 1
                    sleep(0.1)
            else:
                retry_counter = 0
                ret += buf[:nbytes]
                if ret[-1] == 0:
                    break

        return ret

    def get_server_mod_list(self):
        return self.send(ListRequest())

    def get_mod_info(self, modid):
        ret = self.send(GetRequest(modid))
        if ret.type == ErrorMessage.TYPE_STR:
            raise ReturnedErrorMessageError(ret)
        elif ret.type != GetResponse.TYPE_STR:
            raise UnexpectedResponseError(ret)
        return ret[GetResponse.KEY_MOD_DATA]

    def download_file(self, modid, output_dirpath):
        global _currently_downloading
        info = self.get_mod_info(modid)
        output_filepath = path.join(output_dirpath, info['filename'])
        if path.exists(output_filepath):
            raise FileExistsError(output_filepath)

        modsize = info['size']
        bytes_read = 0
        bytes_remaining = modsize

        if modsize == 0:
            raise ValueError('Modsize cannot be 0')
        try:
            _currently_downloading = output_filepath
            with open(output_filepath, 'wb') as file:
                self.sock.send(DownloadRequest(modid).encode())
                buf = bytearray(DOWNLOAD_BUFFER_SIZE)

                attempt_counter = 0
                first_buffer = True
                while bytes_remaining > 0:
                    nbytes = self.sock.recv_into(buf, DOWNLOAD_BUFFER_SIZE)
                    if nbytes == 0:
                        if bytes_remaining > 0:
                            if attempt_counter == 3:
                                raise IncompleteDownloadError('Incomplete download! Expected {} bytes, got {}.'.format(modsize, bytes_read))
                            attempt_counter += 1
                            sleep(0.1)
                    else:
                        # Check for response message instead of regular download (in case of error)
                        if first_buffer:
                            first_buffer = False
                            if buf.startswith(b'{'):
                                # Response message from server instead
                                data = buf[:nbytes]

                                # Handle big messages (future-proofing)
                                if not data.endswith(bytes(1)):
                                    try:
                                        while True:
                                            b = self.sock.recv(DOWNLOAD_BUFFER_SIZE)
                                            if len(b) == 0:
                                                break
                                            data += b
                                            if data.endswith(bytes(1)):
                                                break
                                    except timeout:
                                        raise ServerSyncError('Unexpected termination of server during message parsing. Last received data: {}'.format(data))

                                msg = Message.decode(data)
                                if msg.type == RedirectMessage.TYPE_STR:
                                    url = msg[RedirectMessage.KEY_LINK]
                                    print('[OK] Received redirect isntruction from server: {}'.format(url))
                                    with requests.get(url) as req:
                                        req.raise_for_status()
                                        for chunk in req.iter_content(chunk_size=8192):
                                            nbytes = len(chunk)
                                            bytes_read += nbytes
                                            bytes_remaining -= nbytes
                                            file.write(chunk)
                                            self.on_progress_cb(bytes_read, modsize)
                                    break
                                else:
                                    raise ServerSyncError('Received message from server: {}'.format(msg))

                        attempt_counter = 0
                        file.write(buf[:nbytes])
                        bytes_read += nbytes
                        bytes_remaining -= nbytes
                        if self.on_progress_cb is not None:
                            self.on_progress_cb(bytes_read, modsize)
        except:
            remove(output_filepath)
            raise
        finally:
            _currently_downloading = None


