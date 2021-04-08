import argparse
from serversync.server import *
from serversync import VERSION
import sys


def exit_after_1(code=0):
    print('Exiting in 3...', end='')
    for i in range(3, 0, -1):
        print('\b\b\b\b{}...'.format(i), end='', flush=True)
        sleep(1)
    print('\b\b\b\b\b\b\bnow     ')
    exit(code)


if __name__ == '__main__':
    ap = argparse.ArgumentParser('serversync | Version {}'.format(VERSION))
    ap.add_argument('--server', action='store_const', const='SERVER', dest='mode', help='Server mode',
                    default='DEFAULT')
    ap.add_argument('--install', action='store_const', const='INSTALL', dest='mode',
                    help='Install commands to context menu')
    ap.add_argument('--noGui', action='store_const', const='CLI', dest='mode',
                    help='Run client without gui')
    ap.add_argument('--configGui', action='store_const', const='CONFIG_GUI', dest='mode',
                    help='Open the configuration GUI')
    ap.add_argument('--setProfile', action='store_const', const='SET_PROFILE', dest='mode',
                    help='Set client profile on server to determine server/client-specific mods')
    ap.add_argument('--port', '-p', action='store', type=int, help='Server port')
    ap.add_argument('--passkey', action='store', type=str, help='Server passkey (used for setting client profile)')
    ap.add_argument('--hostname', '-ip', action='store', type=str, help='Server ip address/hostname')

    pargs, unknown = ap.parse_known_args(sys.argv[1:])

    if pargs.mode == 'DEFAULT':
        app = QApplication(sys.argv)
        ex = ClientGUI()
        sys.exit(app.exec_())

    elif pargs.mode == 'CLI':
        client = Client()
        client.on_progress_cb = print_progress

        if pargs.port is not None:
            client.conf.server_port = pargs.port
            client.conf.save()
            print('Updated port in config to {} [OK]'.format(client.conf.server_port))
        if pargs.hostname is not None:
            client.conf.server_ip = pargs.hostname
            client.conf.save()
            print('Updated hostname in config to {} [OK]'.format(client.conf.server_ip))

        local_mods = list_mods_in_dir()

        print('Connecting to server at {}:{}... '.format(client.conf.server_ip, client.conf.server_port), end='')

        required_mods = {}
        optional_mods = {}
        try:
            server_mods = client.get_server_mod_list()
            
            if len(server_mods) == 0:
                print('ERROR')
                print('Server sent no mods')
                exit_after_1(-1)

            required_mods = server_mods['required']
            optional_mods = server_mods['optional']

            print('Received {} mods ({} required, {} optional) [OK]'.format(len(required_mods) + len(optional_mods),
                                                                            len(required_mods), len(optional_mods)))
        except error as e:
            print('ERROR')
            print('Unable to connect to server: {}'.format(e))
            exit_after_1(-1)

        to_update = []
        to_delete = []
        to_add = []

        for mid in local_mods:
            if mid in required_mods:
                local_ver = local_mods[mid].version
                server_ver = required_mods[mid]['version']
                if local_ver is None or local_ver != server_ver:
                    to_update.append(mid)
            elif mid not in optional_mods:
                to_delete.append(local_mods[mid])
        for mid in required_mods:
            if mid not in local_mods:
                to_add.append(required_mods[mid])

        todo = len(to_delete) + len(to_add) + len(to_update)
        if todo == 0:
            print('[OK] Up to date')
            sleep(1)
            exit_after_1(0)

        if len(to_update) > 0:
            print('To Update:')
            for i in to_update:
                mod = local_mods[i]
                print('  o {} ({} -> {})'.format(mod.name, mod.version if mod.version is not None else 'Unknown',
                                                 required_mods[i]['version'] if required_mods[i][
                                                                                    'version'] is not None else 'Unknown'))

        if len(to_add) > 0:
            print('To Add:')
            for i in to_add:
                print('  + {} ({})'.format(i['name'], i['version']))

        if len(to_delete) > 0:
            print('To Delete:')
            for i in to_delete:
                print('  - {} ({})'.format(i.name, i.version))

        print('Summary: Delete {}, Update {}, Download {}'.format(len(to_delete), len(to_update), len(to_add)))

        if not input('Continue? (y/n)').upper().startswith('Y'):
            exit(0)

        done = 1
        tmp = str(len(str(todo)))
        donestr = '[{:' + tmp + '} of {:' + tmp + '}]'
        for i in to_delete:
            print('{:<90} |   0%'.format('{} Deleting: {}... '.format(donestr.format(done, todo), i.name)),
                  end='',
                  flush=True)
            remove(i.filepath)
            print()
            done += 1

        for i in to_update:
            local_mod = local_mods[i]
            remote_mod = client.get_mod_info(i)
            print('{:<90} |   0%'.format('{} Updating: {}{}... '.format(donestr.format(done, todo), local_mod.name,
                                                                        ' to {}'.format(remote_mod['version']) if
                                                                        remote_mod['version'] is not None else '')),
                  end='',
                  flush=True)
            remove(local_mod.filepath)
            client.download_file(i, '.')
            print()
            done += 1

        for i in to_add:
            print('{:<90} |   0%'.format(
                '{} Downloading: {} {}... '.format(donestr.format(done, todo), i['name'], i['version'])), end='',
                  flush=True)
            client.download_file(i['id'], '.')
            print()
            done += 1

        print('[OK] Sync completed!')

    elif pargs.mode == 'SERVER':
        server = ServerSyncServer(pargs.port, pargs.passkey)
        server.run()

    elif pargs.mode == 'INSTALL':
        from serversync.config_gui import *
        import winreg
        if sys.platform != 'win32':
            print('[ER] Unsupported platform')
            exit(1)

        key_path = r"Directory\\Background\\shell\\ServerSync"
        key = winreg.CreateKeyEx(winreg.HKEY_CLASSES_ROOT, key_path)
        key2 = winreg.CreateKeyEx(key, r"command")

        def is_installed():
            # winreg.QueryValue(key, '')
            return False

        sel = input('Please select an option: \n'
                    '  1  Add ServerSync to context menu\n'
                    '  2  Remove ServerSync from context menu\n'
                    'Selection: ')

        if sel == '1':
            print('Installing...')
            install_context_menu()
            print('DONE')
        elif sel == '2':
            print('Uninstalling...')
            print('  Removing command subkey... ', end='')
            winreg.DeleteKey(key2, '')
            print('[OK]')
            print('  Removing ServerSync key... ', end='')
            winreg.DeleteKey(key, '')
            print('[OK]')

        else:
            print('Unrecognised selection: "{}". Exiting.'.format(sel))
            exit(0)
    elif pargs.mode == 'CONFIG_GUI':
        from serversync.config_gui import config_editor_session
        config_editor_session()
    elif pargs.mode == 'SET_PROFILE':
        print('Building profile')
        modlist = list_mods_in_dir()
        profile = {mid: modlist[mid].to_dict() for mid in modlist}
        cli = Client()
        print('Connecting & Uploading to server... ', end='')
        to_send = {'type': 'set_profile', 'mods': profile}
        if pargs.passkey is not None:
            to_send['passkey'] = pargs.passkey

        ret = cli.send(json.dumps(to_send).encode())
        if ret is not None:
            if ret['type'] == 'error':
                if 'code' in ret and ret['code'] == 1:
                    passkey = input('Enter passkey: ')
                    to_send['passkey'] = passkey
                    ret = cli.send(json.dumps(to_send).encode())
                    if ret is not None:
                        if ret['type'] == 'error':
                            print('[ER] Error when uploading to server: {}'.format(ret['message']), file=sys.stderr)
                            exit(ret['code'] if 'code' in ret else -1)
                        elif ret['type'] != 'success':
                            print('[WN] Unhandled response: {}'.format(ret))
                else:
                    print('[ER]')
                    print(ret['message'])
                    exit(-1)
            elif ret['type'] != 'success':
                print('[WN] Unhandled response: {}'.format(ret))
        print('[OK]', flush=True)

        server_modlist = cli.get_server_mod_list()
        optional = server_modlist['optional']
        server_side = server_modlist['server-side']

        print('Required mods:')
        for mid in server_modlist['required']:
            print('  - {}'.format(cli.get_mod_info(mid)['name']))

        print('Client-side mods:')
        for mid in optional:
            print('  - {}'.format(modlist[mid].name))

        print('Server-side mods:')
        for mid in server_side:
            print('  - {}'.format(cli.get_mod_info(mid)['name']))




