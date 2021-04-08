from os import path, listdir, getcwd, remove
import zipfile
import json
import toml


DEFAULT_SERVER_PORT = 25567
INPUT_BUFFER_SIZE = 1048576
DOWNLOAD_BUFFER_SIZE = 1048576
CONFIG_FILENAME = 'serversync.conf'

CONF_KEY_KNOWN_CLIENT_SIDE_MODS = 'known_client_side_mods'
CONF_KEY_KNOWN_SERVER_SIDE_MODS = 'known_server_side_mods'


def parse_jar_manifest(data: str):
    manifestkeys = ['Name', 'Specification-Title', 'Specification-Vendor', 'Specification-Version',
                    'Implementation-Title', 'Implementation-Version', 'Implementation-Vendor', 'Implementation-URL',
                    'Extension-Name', 'Comment']
    manifestkeys = [i.replace('-', '').lower() for i in manifestkeys]
    manifest = []
    current = {}
    lines = data.splitlines()
    idx = 0
    while idx<len(lines):
        line = lines[idx].strip()
        if len(line) > 0:
            splits = line.split(':')
            key = splits[0].lower().strip().replace('-','')
            if key in manifestkeys:
                value = ':'.join(splits[1:]).strip()
                current[key] = value
                while len(line.encode('utf-8')) >= 70:
                    if idx < len(lines)-1:
                        next_line = lines[idx+1]
                        if next_line[0] == ' ':
                            current[key] += next_line.strip()
                            idx += 1
                            line = next_line
                            continue
                    break
        elif len(current) > 0:
            count = len(current.values())
            # We need to weed out name only entries
            # We can manually interrogate packages
            if count > 1 or (count == 1 and 'name' not in current.keys()):
                manifest.append(current)
            current = {}
        idx += 1
    if current != {}:
        manifest.append(current)
    return manifest


class ModInfo:
    def __init__(self, filepath):
        self.filepath = filepath
        if not path.exists(filepath):
            raise FileNotFoundError(filepath)
        if not zipfile.is_zipfile(filepath):
            remove(filepath)
            raise zipfile.BadZipFile(filepath)
        zfile = zipfile.ZipFile(filepath, 'r')
        self.fabric = False
        try:
            modsinfo = toml.loads(zfile.read('META-INF/mods.toml').decode())
            if len(modsinfo['mods']) > 1:
                raise ValueError('jar files with more than 1 mod is not currently supported!')
            self.config = modsinfo['mods'][0]
        except KeyError as e:
            try:
                fabric_conf = json.loads(zfile.read('fabric.mod.json').decode())
                self.config = {'displayName': fabric_conf['name'],
                               'version': fabric_conf['version'],
                               'modId': fabric_conf['id']}
                self.fabric = True
            except:
                raise KeyError('No META-INF/mods.toml or fabric.mod.json found in mod file: {}!'.format(self.filepath))
        try:
            self.manifest = parse_jar_manifest(zfile.read('META-INF/MANIFEST.MF').decode())
        except KeyError:
            self.manifest = None
        pass

    @property
    def name(self):
        return self.config['displayName']

    @property
    def version(self):
        ver = self.config['version']
        if ver == '${file.jarVersion}':
            try:
                ver = self.manifest[0]['implementationversion']
            except IndexError:
                return None
        return ver

    @property
    def id(self):
        return self.config['modId']

    def to_dict(self):
        return {
            'name': self.name,
            'id': self.id,
            'version': self.version,
            'filename': path.basename(self.filepath),
            'size': path.getsize(self.filepath)
        }


class ClientConfig(dict):
    def __init__(self):
        super().__init__()
        self.reload()

    @property
    def server_ip(self):
        return self['server_ip']

    @property
    def server_port(self):
        return self['server_port']

    @server_ip.setter
    def server_ip(self, ip: str):
        self['server_ip'] = ip

    @server_port.setter
    def server_port(self, port: int):
        self['server_port'] = port

    @property
    def server_address(self):
        if self.server_ip is None:
            raise ValueError('No IP has been set')
        return self.server_ip, self.server_port

    def save(self):
        with open(CONFIG_FILENAME, 'w') as file:
            file.write(json.dumps(self))

    def reload(self):
        self.clear()
        self.update({'server_port': DEFAULT_SERVER_PORT, 'server_ip': 'marcobolt.com'})
        if path.exists(CONFIG_FILENAME):
            with open(CONFIG_FILENAME, 'r') as file:
                self.update(json.loads(file.read()))


def list_mods_in_dir(dirpath='.', custom_progress_callback = None) -> [ModInfo]:
    print('Compiling list of mods...   0%', end='', flush=True)
    to_ret = {}
    files = [f for f in listdir(dirpath) if f.endswith('.jar')]
    nfiles = len(files)
    for i in range(nfiles):
        f = files[i]
        try:
            m = ModInfo(path.join(dirpath, f))
            to_ret[m.id] = m
        except KeyError as e:
            print('[WN] {}: {}'.format(f, e))
        except zipfile.BadZipFile as e:
            print('[WN]: {}. Deleted.'.format(e))

        prog = int(100*(i+1)/nfiles)
        print('\b\b\b\b{:>3}%'.format(prog), end='', flush=True)
        if custom_progress_callback is not None:
            custom_progress_callback(prog)
    print('\b\b\b\b\b  Found {} mods [OK]'.format(len(to_ret)))
    return to_ret


def print_progress(cur, total):
    percent = int(100 * cur / total)
    print('\b\b\b\b{:>3}%'.format(percent), end='', flush=True)
