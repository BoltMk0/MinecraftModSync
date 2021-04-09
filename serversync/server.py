from serversync.client import *
from time import sleep
from socket import timeout


class ServerSyncServer:
    def __init__(self, port: int = None, passkey=None):
        self.conf = ClientConfig()
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

    @property
    def client_side_mod_ids(self):
        return self.conf[CONF_KEY_KNOWN_CLIENT_SIDE_MODS] if CONF_KEY_KNOWN_CLIENT_SIDE_MODS in self.conf else []

    @property
    def server_side_mod_ids(self):
        return self.conf[CONF_KEY_KNOWN_SERVER_SIDE_MODS] if CONF_KEY_KNOWN_SERVER_SIDE_MODS in self.conf else []

    def filter_non_sided_mods(self, modlist: dict):
        client_only_mod_ids = self.client_side_mod_ids
        server_only_mod_ids = self.server_side_mod_ids
        to_del = []
        for modid in modlist:
            if modid in client_only_mod_ids or modid in server_only_mod_ids:
                to_del.append(modid)
        server_only_mod_ids = {}
        for modid in to_del:
            server_only_mod_ids[modid] = modlist[modid]
            del modlist[modid]

        return modlist, server_only_mod_ids

    def run(self):
        while True:
            server_sock = socket(AF_INET, SOCK_STREAM)
            modlist = list_mods_in_dir()
            self.conf.reload()
            modlist, server_only_mods= self.filter_non_sided_mods(modlist)
            print('[OK] Filtered down to {} shared mods'.format(len(modlist.keys())))
            try:
                print('Starting server on port {}... '.format(self.conf.server_port), end='')
                try:
                    server_sock.bind(('', self.conf.server_port))
                    print('[OK]')
                except:
                    print('[ER]')
                    raise

                server_sock.listen(5)
                while True:
                    cli, addr = server_sock.accept()
                    print('[OK] Client connected: {}'.format(addr))
                    msg = b''
                    cli.settimeout(0.5)
                    try:
                        while True:
                            buf = cli.recv(INPUT_BUFFER_SIZE)
                            if len(buf) == 0:
                                break
                            # If null-byte terminated, end of message
                            if buf.endswith(bytes(1)):
                                msg += buf[:-1]
                                break
                            else:
                                msg += buf
                    except timeout:
                        pass

                    if msg == b'ping':
                        print('Handling ping request')
                        cli.send('pong'.encode())
                    else:
                        if msg == b'list':
                            print('Handling list request')
                            cli.send(json.dumps({'required': {mid: modlist[mid].to_dict() for mid in modlist},
                                                 'optional': self.client_side_mod_ids,
                                                 'server-side': self.server_side_mod_ids}).encode())

                        elif msg.startswith(b'get '):
                            msg = msg.decode()
                            mod_id = msg.lstrip('get').strip()
                            print('Handling get request: {}'.format(mod_id))
                            if mod_id in modlist:
                                cli.send(json.dumps(modlist[mod_id].to_dict()).encode())
                            elif mod_id in server_only_mods:
                                cli.send(json.dumps(server_only_mods[mod_id].to_dict()).encode())

                        elif msg.startswith(b'download '):
                            msg = msg.decode()
                            mod_id = msg.lstrip('download').strip()
                            print('Handling download request: {}'.format(mod_id))
                            print('  Received download request for mod with id: {}'.format(mod_id))
                            if mod_id in modlist:
                                mod = modlist[mod_id]
                                print('  Uploading {}...   0%'.format(mod.filepath), end='')
                                with open(mod.filepath, 'rb') as ifile:
                                    total_sent = 0
                                    to_send = path.getsize(mod.filepath)
                                    try:
                                        while True:
                                            buf = ifile.read(DOWNLOAD_BUFFER_SIZE)
                                            if len(buf) == 0:
                                                break
                                            cli.send(buf)
                                            total_sent += len(buf)
                                            print_progress(total_sent, to_send)
                                    except timeout:
                                        print(' [ER] Timed out')
                            else:
                                print('[ER] Mod with id {} not in modlist?!'.format(mod_id))
                        else:
                            try:
                                msg = Message.decode(msg)
                                if msg.type == PingMessage.TYPE_STR:
                                    cli.send(PingMessage().encode())
                                elif msg.type == ListRequest.TYPE_STR:
                                    cli.send(ListResponse({mid: modlist[mid].to_dict() for mid in modlist},
                                                          self.client_side_mod_ids,
                                                          self.server_side_mod_ids).encode())
                                elif msg.type == GetRequest.TYPE_STR:
                                    mod_id = msg[GetRequest.KEY_ID]
                                    if mod_id in modlist:
                                        cli.send(GetResponse(modlist[mod_id]).encode())
                                    elif mod_id in server_only_mods:
                                        cli.send(GetResponse(server_only_mods[mod_id]).encode())
                                    else:
                                        cli.send(ErrorMessage(GetRequest.ERROR_NOT_FOUND).encode())
                                elif msg.type == DownloadRequest.TYPE_STR:
                                    mod_id = msg[DownloadRequest.KEY_ID]
                                    print('Handling download request: {}'.format(mod_id))
                                    print('  Received download request for mod with id: {}'.format(mod_id))
                                    if mod_id in modlist:
                                        mod = modlist[mod_id]
                                        print('  Uploading {}...   0%'.format(mod.filepath), end='')
                                        with open(mod.filepath, 'rb') as ifile:
                                            total_sent = 0
                                            to_send = path.getsize(mod.filepath)
                                            try:
                                                while True:
                                                    buf = ifile.read(DOWNLOAD_BUFFER_SIZE)
                                                    if len(buf) == 0:
                                                        break
                                                    cli.send(buf)
                                                    total_sent += len(buf)
                                                    print_progress(total_sent, to_send)
                                            except timeout:
                                                print('[ER] Timed out')
                                    else:
                                        print('[ER] Mod with id {} not in modlist?!'.format(mod_id))
                                elif msg.type == SetProfileRequest.TYPE_STR:
                                    if self.passkey is not None:
                                        cli_passkey = msg[SetProfileRequest.KEY_PASSKEY]
                                        if cli_passkey is None:
                                            print('[WN] Client profile set failed due to missing passkey')
                                            cli.send(ErrorMessage(SetProfileRequest.ERROR_CODE_MISSING_PASSKEY, 'Passkey is missing from request').encode())
                                            raise ValueError('Missing passkey')
                                        if cli_passkey != self.passkey:
                                            print('[WN] Client profile set failed due to invalid passkey: "{}"'.format(cli_passkey))
                                            cli.send(ErrorMessage(SetProfileRequest.ERROR_CODE_INVALID_PASSKEY, 'Invalid passkey').encode())
                                            raise ValueError('Invalid passkey: {}'.format(cli_passkey))

                                    print('Handling set_profile request')
                                    client_mods = msg[SetProfileRequest.KEY_CLIENT_MODS]
                                    client_only_mod_ids = []
                                    server_only_mod_ids = []

                                    # Re-combine server-only mods with modlist
                                    modlist.update(server_only_mods)

                                    for mid in client_mods:
                                        if mid not in modlist:
                                            if mid not in client_only_mod_ids:
                                                client_only_mod_ids.append(mid)

                                    for mid in modlist:
                                        if mid not in client_mods:
                                            if mid not in server_only_mod_ids:
                                                server_only_mod_ids.append(mid)

                                    self.conf[CONF_KEY_KNOWN_CLIENT_SIDE_MODS] = client_only_mod_ids
                                    self.conf[CONF_KEY_KNOWN_SERVER_SIDE_MODS] = server_only_mod_ids

                                    self.conf.save()

                                    cli.send(SuccessMessage().encode())

                                    print('[OK] Client profile updated')
                                    modlist = list_mods_in_dir()
                                    modlist, server_only_mods = self.filter_non_sided_mods(modlist)
                                    print('[OK] Filtered down to {} shared mods'.format(len(modlist.keys())))
                                else:
                                    cli.send(ErrorMessage(ErrorMessage.ERROR_CODE_UNRECOGNISED_REQUEST, 'Unknown request type: {}'.format(msg.type)).encode())
                            except ValueError:
                                pass

                    cli.close()
                    print('[OK] Disconnected client.')
            except OSError as e:
                print(e, file=sys.stderr)
                # Filter out exception when client forcibly closes connection
                if e.errno != 10054:
                    break
            except KeyboardInterrupt:
                print('[OK] Closing server')
                server_sock.close()
                break
            except Exception as e:
                print(e, file=sys.stderr)
                server_sock.close()
                print('Restarting...')
                sleep(1)
        print('[OK] Server stopped')
