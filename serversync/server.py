from serversync.client import *
from time import sleep
from socket import timeout
import select
from threading import Thread, Lock, ThreadError
from os import makedirs
from shutil import rmtree, copy
import requests
from flask import Flask, send_file, abort


DEFAULT_HTTP_SERVER_PORT = 25568
CONF_KEY_HTTP_SERVER_PORT = 'http_server_port'
CONF_KEY_REDIRECT_MIN_MODSIZE = 'redirect_min_modsize'
DEFAULT_REDIRECT_MIN_MODSIZE = 1048576


class NoModsFoundError(Exception):
    pass


class ServerSyncServer():
    class ModCache(dict):
        CACHE_DIR = '.serversync_cache'
        """
        Manager for caching all mods at server launch (in case of mod changes during server runtime)
        """
        def __init__(self, cache_dir=None):
            if cache_dir is None:
                cache_dir = self.CACHE_DIR
            self.cachedir = cache_dir
            self.preloaded = []
            self.clear()

        def from_filename(self, filename):
            filepath = path.join(self.cachedir, filename)
            return ModInfo(filepath)

        def __del__(self):
            print('[OK] Cleaning cache dir')
            rmtree(self.cachedir)

        def preload(self, mod: ModInfo):
            cached_file = path.join(self.cachedir, path.basename(mod.filepath))
            copy(mod.filepath, cached_file)
            self.preloaded.append(cached_file)

        def reload(self):
            self.clear()
            print('Scanning local dir for mods...   0%', end='')
            modlist = list_mods_in_dir(custom_progress_callback=print_progress)
            nmods = len(modlist)
            print('\b\b\b\bfound {} mods [OK]'.format(nmods))
            print('Building mod cache...   0%', end='')
            counter = 0
            for m_id in modlist:
                self.add_mod(modlist[m_id])
                counter += 1
                print_progress(int(100*counter/nmods))
            print('\b\b\b\b[OK]')

        def clear(self):
            if path.exists(self.cachedir):
                rmtree(self.cachedir)
            makedirs(self.cachedir)
            super().clear()

        def add_mod(self, mod: ModInfo):
            cached_file = path.join(self.cachedir, path.basename(mod.filepath))
            if cached_file in self.preloaded:
                self.preloaded.remove(cached_file)
            else:
                copy(mod.filepath, cached_file)
            self[mod.id] = ModInfo(cached_file)

    class ClientHandler:
        def __init__(self, cli: socket, addr):
            self.sock = cli
            self.addr = addr
            self.version_major = -1
            self.version_minor = -1
            self.input_buffer = bytes()
            self.output_buffer = bytes()
            self.redirect_supported = False

        def single_message_mode(self):
            # Client 1.3+ operates multi-message mode
            return self.version_major < 1 or (self.version_major == 1 and self.version_minor < 3)

        def update_client_data_from_ping(self, msg: Message):
            if PingMessage.KEY_VERSION in msg:
                self.version_major, self.version_minor, build = version_numbers_from_version_string(msg[PingMessage.KEY_VERSION])

            if PingMessage.KEY_SUPPORTS_HTTP_REDIRECT in msg:
                self.redirect_supported = msg[PingMessage.KEY_SUPPORTS_HTTP_REDIRECT]
            else:
                self.redirect_supported = False

            print('[OK] Client Info updated: Address: {} | Version {}.{} | Allows redirects: {}'.format(self.addr, self.version_major, self.version_minor, self.redirect_supported))

        def ingest(self, buf: bytearray, nbytes: int):
            self.input_buffer += buf[:nbytes]

        def message_at_input(self):
            return bytes(1) in self.input_buffer

        def iter_messages_at_input(self) -> Message:
            while bytes(1) in self.input_buffer:
                msg_data, self.input_buffer = self.input_buffer.split(bytes(1), 1)
                yield Message.decode(msg_data)

        def send(self, data: bytes):
            self.output_buffer += data

        def has_output_data(self):
            return len(self.output_buffer) > 0

        def has_input_data(self):
            return len(self.input_buffer) > 0

        def write_output_packet(self):
            n_sent = self.sock.send(self.output_buffer[:DOWNLOAD_BUFFER_SIZE])
            self.output_buffer = self.output_buffer[n_sent:]

    def __init__(self, port: int = None, passkey=None):
        self.conf = ServerSyncConfig()
        if port is not None:
            self.conf.server_port = port
            self.conf.save()
            print('[OK] Server port updated to {}.'.format(port))

        if 'passkey' not in self.conf:
            self.conf['passkey'] = None

        if passkey is not None:
            self.conf['passkey'] = passkey
            self.conf.save()
            print('[OK] Server passkey set to "{}".'.format(passkey))

        self.passkey = self.conf['passkey']

        self.message_handle_map = {
            PingMessage.TYPE_STR: self._handle_ping,
            GetRequest.TYPE_STR: self._handle_get,
            ListRequest.TYPE_STR: self._handle_list,
            DownloadRequest.TYPE_STR: self._handle_download,
            SetProfileRequest.TYPE_STR: self._handle_set_profile,
            ServerRefreshRequest.TYPE_STR: self._handle_refresh_request,
            ServerStopRequest.TYPE_STR: self._handle_stop_request
        }

        self.modcache = self.ModCache()

        self.client_side_modlist = {}
        self.modcache_lock = Lock()

        self._modlist_updater_thread = None

        self.server_sock = None
        self.running = False
        self._input_sockets = []
        self._output_sockets = []

        self.client_handlers = {}

        self.http_server = None
        self.http_server_thread = None

    @staticmethod
    def public_ip():
        return requests.get('https://api.ipify.org').text

    @property
    def http_server_port(self):
        if CONF_KEY_HTTP_SERVER_PORT not in self.conf:
            self.conf[CONF_KEY_HTTP_SERVER_PORT] = DEFAULT_HTTP_SERVER_PORT
            self.conf.save()
        return self.conf[CONF_KEY_HTTP_SERVER_PORT]

    @property
    def client_side_mod_ids(self):
        if CONF_KEY_KNOWN_CLIENT_SIDE_MODS not in self.conf:
            self.conf[CONF_KEY_KNOWN_CLIENT_SIDE_MODS] = []
        return self.conf[CONF_KEY_KNOWN_CLIENT_SIDE_MODS]

    @client_side_mod_ids.setter
    def client_side_mod_ids(self, mids: [str]):
        self.conf[CONF_KEY_KNOWN_CLIENT_SIDE_MODS] = mids

    @property
    def server_side_mod_ids(self):
        if CONF_KEY_KNOWN_SERVER_SIDE_MODS not in self.conf:
            self.conf[CONF_KEY_KNOWN_SERVER_SIDE_MODS] = []
        return self.conf[CONF_KEY_KNOWN_SERVER_SIDE_MODS] if CONF_KEY_KNOWN_SERVER_SIDE_MODS in self.conf else []

    @server_side_mod_ids.setter
    def server_side_mod_ids(self, mids: [str]):
        self.conf[CONF_KEY_KNOWN_SERVER_SIDE_MODS] = mids

    def _handle_legacy(self, client: ClientHandler, msg: bytes):
        # Strip off any null bytes
        if msg.endswith(bytes(1)):
            msg = msg.rstrip(bytes(1))

        if msg == b'ping':
            print('Handling ping request')
            client.send('pong'.encode())
        elif msg == b'list':
                print('Handling list request')
                required = {}
                for mid in self.modcache:
                    if mid in self.server_side_mod_ids:
                        continue
                    try:
                        required[mid] = self.modcache[mid].to_dict()
                    except FileNotFoundError as e:
                        print('[ER] {}'.format(str(e)))
                        del self.modcache[mid]
                        print('WARNING: Mod with id {} removed Resolved. Removed from modlist'.format(mid))

                client.send(json.dumps({'required':required,
                                        'optional': self.client_side_mod_ids,
                                        'server-side': self.server_side_mod_ids}).encode())

        elif msg.startswith(b'get '):
            msg = msg.decode()
            mod_id = msg.lstrip('get').strip()
            print('Handling get request: {}'.format(mod_id))
            try:
                client.send(json.dumps(self.modcache[mod_id].to_dict()).encode())
            except KeyError:
                print('[ER] Unknown mod: {}'.format(mod_id))

        elif msg.startswith(b'download '):
            msg = msg.decode()
            mod_id = msg.lstrip('download').strip()
            print('Handling download request: {}'.format(mod_id))
            print('  Received download request for mod with id: {}'.format(mod_id))
            try:
                mod = self.modcache[mod_id]
                print('  Uploading {}...   0%'.format(mod.filepath), end='')
                with open(mod.filepath, 'rb') as ifile:
                    total_sent = 0
                    to_send = path.getsize(mod.filepath)
                    while True:
                        buf = ifile.read(DOWNLOAD_BUFFER_SIZE)
                        if len(buf) == 0:
                            break
                        client.send(buf)
                        total_sent += len(buf)
                        print_progress(int(100*to_send/total_sent))
            except timeout:
                print(' [ER] Timed out')
            except KeyError:
                print('[ER] Mod with id {} not in modlist'.format(mod_id))
        else:
            print('[ER] Unrecognised legacy request: {}'.format(msg))

    def _handle_ping(self, client: ClientHandler, msg: Message):
        client.update_client_data_from_ping(msg)
        ret_mst = PingMessage()
        ret_mst[PingMessage.KEY_SUPPORTS_HTTP_REDIRECT] = True
        client.send(ret_mst.encode())

    def _handle_get(self, client: ClientHandler, msg: Message):
        mod_id = msg[GetRequest.KEY_ID]
        try:
            client.send(GetResponse(self.modcache[mod_id]).encode())
        except KeyError:
            client.send(ErrorMessage(GetRequest.ERROR_NOT_FOUND).encode())

    def _handle_list(self, client: ClientHandler, msg: Message):
        client.send(ListResponse(
            required={mid: self.modcache[mid].to_dict() for mid in self.modcache if mid not in self.server_side_mod_ids},
            clientside=self.client_side_mod_ids,
            serverside=self.server_side_mod_ids).encode())

    def _handle_download(self, client: ClientHandler, msg: Message):
        mod_id = msg[DownloadRequest.KEY_ID]
        print('Handling download request: {}'.format(mod_id))
        try:
            mod = self.modcache[mod_id]
            redirect_size = self.conf[CONF_KEY_REDIRECT_MIN_MODSIZE]
            if client.redirect_supported and self.http_server is not None and \
                    redirect_size < mod.size:
                public_ip = self.public_ip()
                mod_filename = path.basename(mod.filepath)
                url = 'http://{}:{}/download/{}'.format(public_ip, self.http_server_port, mod_filename)
                client.send(RedirectMessage(mod.id, url).encode())
                print('[OK] Redirected client to {}'.format(url))
            else:
                with open(mod.filepath, 'rb') as file:
                    client.output_buffer = file.read()
                print('[OK] Uploading {} ({} bytes loaded into output buffer)'.format(mod.name, len(client.output_buffer)))

        except KeyError:
            print('[ER] Mod with id {} not in modlist'.format(mod_id))
            if client.single_message_mode():
                self._close_client(client.sock)
            else:
                client.send(ErrorMessage(DownloadRequest.ERROR_NOT_FOUND, mod_id).encode())

    def _handle_set_profile(self, client: ClientHandler, msg: Message):
        if self.passkey is not None:
            cli_passkey = msg[SetProfileRequest.KEY_PASSKEY]
            if cli_passkey is None:
                print('[WN] Client profile set failed due to missing passkey')
                client.send(ErrorMessage(SetProfileRequest.ERROR_CODE_MISSING_PASSKEY,
                                      'Passkey is missing from request').encode())
                raise ValueError('Missing passkey')
            if cli_passkey != self.passkey:
                print('[WN] Client profile set failed due to invalid passkey: "{}"'.format(cli_passkey))
                client.send(ErrorMessage(SetProfileRequest.ERROR_CODE_INVALID_PASSKEY, 'Invalid passkey').encode())
                raise ValueError('Invalid passkey: {}'.format(cli_passkey))

        print('Handling set_profile request')
        client_mods = msg[SetProfileRequest.KEY_CLIENT_MODS]

        client_only_mod_ids = []
        server_only_mod_ids = []

        if self.modcache_lock.acquire(True, 1):
            try:
                for mid in client_mods:
                    if mid not in self.modcache:
                        if mid not in client_only_mod_ids:
                            client_only_mod_ids.append(mid)

                for mid in self.modcache:
                    if mid not in client_mods:
                        if mid not in server_only_mod_ids:
                            server_only_mod_ids.append(mid)

                self.client_side_mod_ids = client_only_mod_ids
                self.server_side_mod_ids = server_only_mod_ids

                self.conf.save()

                client.send(SuccessMessage().encode())
                print('[OK] Client profile updated')

            except:
                raise
            finally:
                self.modcache_lock.release()

    def _handle_refresh_request(self, client: ClientHandler, msg: Message):
        self.launch_modlist_update_thread()
        client.send(SuccessMessage().encode())

    def _handle_stop_request(self, client: ClientHandler, msg: Message):
        if client.addr[0] == '127.0.0.1':
            self.server_sock.close()
            self.running = False
            # Directly send success message before closing
            client.sock.send(SuccessMessage().encode())
        client.sock.send(ErrorMessage(message='Not allowed to close server from another machine!').encode())

    def _handle_unknown(self, client: ClientHandler, msg: Message):
        print('[ER] Unknown message type: {}'.format(msg.type))
        client.send(ErrorMessage(ErrorMessage.ERROR_CODE_UNRECOGNISED_REQUEST, 'Unknown request type: {}'.format(msg.type)).encode())

    def handle_message_data(self, client: ClientHandler, data: bytes):
        """
        Top-level method for handling all messages (legacy and current).
        Ensures thread-safe access of server attributes.
        :param client:
        :param data:
        :return:
        """
        if not self.modcache_lock.acquire(True, 1):
            client.send(ErrorMessage(message='ServerError: Unable to aquire modlist lock. Please contact your administrator.').encode())
            raise ThreadError('Unable to aquire modlist lock')
        try:
            msg = Message.decode(data)
            self.message_handle_map.get(msg.type, self._handle_unknown)(client, msg)
        except json.JSONDecodeError:
            self._handle_legacy(client, data)
        except ValueError:
            pass
        finally:
            self.modcache_lock.release()

    def _close_client(self, sock: socket):
        sock.close()
        if sock in self.client_handlers:
            print('[OK] Client connection closed {}'.format(self.client_handlers[sock].addr))
            del self.client_handlers[sock]
        else:
            print('[OK] Socket closed: {}'.format(sock))
        self._input_sockets.remove(sock)
        if sock in self._output_sockets:
            self._output_sockets.remove(sock)

    def run(self):
        self.running = True

        self.server_sock = socket(AF_INET, SOCK_STREAM)
        self.server_sock.setblocking(False)
        self._input_sockets.append(self.server_sock)

        # Refresh modlist first
        self.modcache_lock.acquire(True, 10)
        self.modcache.reload()
        self.modcache_lock.release()
        if len(self.modcache) == 0:
            raise NoModsFoundError('[ER] No mods found in dir! Please run server in mods dir!')
        print(' Found {} mods'.format(len(self.modcache)))

        self.conf.reload()

        print('Starting server on port {}... '.format(self.conf.server_port), end='')
        try:
            self.server_sock.bind(('', self.conf.server_port))
            print('[OK]')

            if self.conf.allow_redirects:
                print('Starting HTTP redirect server... ')
                if CONF_KEY_REDIRECT_MIN_MODSIZE not in self.conf:
                    self.conf[CONF_KEY_REDIRECT_MIN_MODSIZE] = DEFAULT_REDIRECT_MIN_MODSIZE
                    self.conf.save()

                self.http_server = Flask(__name__)
                self.http_server_thread = Thread(target=self.http_server.run, args=('0.0.0.0', self.http_server_port))

                @self.http_server.route('/download/<filename>')
                def handle_mod_download(filename):
                    if self.modcache_lock.acquire(True, 5):
                        try:
                            mod = self.modcache.from_filename(filename)
                            return send_file(mod.filepath)
                        except Exception as e:
                            return abort(404)
                        finally:
                            self.modcache_lock.release()
                    else:
                        return abort(500)

                @self.http_server.route('/conf')
                def get_conf():
                    return json.dumps({k: self.conf[k] for k in self.conf if k not in ['passkey']}, indent=4)

                @self.http_server.route('/list')
                def get_list():
                    if self.modcache_lock.acquire(True, 10):
                        try:
                            return json.dumps([self.modcache[mid].to_dict() for mid in self.modcache], indent=4)
                        except:
                            raise
                        finally:
                            self.modcache_lock.release()

                self.http_server_thread.start()
                test_url = 'http://{}:{}/conf'.format(self.public_ip(), self.http_server_port)
                try:
                    requests.get(test_url)
                    print('[OK] Confirmed HTTP server is running and reachable.')
                except Exception as e:
                    print('[ER] HTTP get attempt failed: {}.\n{}\nDisabling http server.'.format(test_url, e))
                    self.http_server = None

            self.server_sock.listen(5)
            self.server_sock.settimeout(60)
            buf = bytearray(DOWNLOAD_BUFFER_SIZE)
            while self.running:
                readable, writeable, exceptional = select.select(self._input_sockets, self._output_sockets, self._input_sockets)
                for sock in readable:
                    if sock is self.server_sock:
                        connection, addr = self.server_sock.accept()
                        connection.setblocking(False)
                        print('[OK] Client connected: {}'.format(addr))
                        handler = self.ClientHandler(connection, addr)
                        self._input_sockets.append(connection)
                        self.client_handlers[connection] = handler
                    else:
                        client = self.client_handlers[sock]
                        # Read available data into buffer
                        try:
                            nbytes = sock.recv_into(buf, DOWNLOAD_BUFFER_SIZE)
                            client.ingest(buf, nbytes)

                            if nbytes > 0:
                                if client.input_buffer.startswith(b'{'):
                                    for msg in client.iter_messages_at_input():
                                        self.message_handle_map.get(msg.type, self._handle_unknown)(client, msg)
                                else:
                                    # Handle legacy case
                                    self._handle_legacy(client, client.input_buffer)

                                if client.has_output_data():
                                    self._output_sockets.append(client.sock)
                                else:
                                    if client.single_message_mode():
                                        self._close_client(sock)
                            if nbytes == 0:
                                # Socket closed
                                self._close_client(sock)

                        except ConnectionResetError:
                            print('[ER] Connection reset {}'.format(client.addr))
                            self._close_client(sock)
                            continue

                for sock in writeable:
                    if sock in self.client_handlers:
                        client = self.client_handlers[sock]
                        client.write_output_packet()
                        if not client.has_output_data():
                            self._output_sockets.remove(sock)
                            if client.single_message_mode():
                                self._close_client(client.sock)

                for sock in exceptional:
                    if sock != self.server_sock:
                        self._close_client(sock)
                    else:
                        self.running = False
        except:
            raise
        finally:
            print('Stopping server...')
            for sock in self._input_sockets:
                if sock != self.server_sock:
                    self._close_client(sock)
            self.server_sock.close()
            print('[OK] Server stopped')

    @staticmethod
    def _modlist_update_thread_func(server, repeat_after=None):
        while True:
            modlist = list_mods_in_dir()

            for mid in modlist:
                mod = modlist[mid]
                if mid not in server.modcache:
                    server.modcache.preload(mod)

            server.modcache_lock.acquire(True, 10)
            to_del = []
            for mid in server.modcache:
                if mid not in modlist:
                    to_del.append(mid)

            for mid in to_del:
                del server.modcache[mid]

            for mid in modlist:
                mod = modlist[mid]
                if mid not in server.modcache:
                    server.modcache.add_mod(mod)

            server.modcache_lock.release()

            if repeat_after is None:
                server.modlist_updater_thread = None
                break

            sleep(repeat_after)

    def launch_modlist_update_thread(self, repeat_after=None):
        if self._modlist_updater_thread is None or not self._modlist_updater_thread.is_alive():
            print('[OK] Spawning new modlist updater thread')
            self._modlist_updater_thread = Thread(target=ServerSyncServer._modlist_update_thread_func,
                                                  args=[self, repeat_after])
            # This thread will not stop program from exiting
            self._modlist_updater_thread.setDaemon(True)
            self._modlist_updater_thread.start()
        else:
            raise ValueError('modlist updater already running')
