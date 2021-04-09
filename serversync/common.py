from os import path, listdir, getcwd, remove
import zipfile
import json
import toml
from serversync import VERSION


DEFAULT_SERVER_PORT = 25567
INPUT_BUFFER_SIZE = 1048576
DOWNLOAD_BUFFER_SIZE = 4096
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
    def __init__(self, filepath=CONFIG_FILENAME):
        super().__init__()
        self.filepath = filepath
        self.reload()

    def exists(self):
        return path.exists(self.filepath)

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
        with open(self.filepath, 'w') as file:
            file.write(json.dumps(self))

    def reload(self):
        self.clear()
        self.update({'server_port': DEFAULT_SERVER_PORT, 'server_ip': 'localhost'})
        if path.exists(self.filepath):
            with open(self.filepath, 'r') as file:
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


class ReturnedErrorMessageError(Exception):
    pass


class UnexpectedResponseError(Exception):
    pass


class Message(dict):
    TYPE_STR = 'message'
    KEY_TYPE = 'type'

    def __init__(self, type: str = None):
        if type is None:
            type = self.TYPE_STR
        super().__init__()
        self.type = type

    @property
    def type(self):
        return self[self.KEY_TYPE]

    @type.setter
    def type(self, t: str):
        self[self.KEY_TYPE] = t

    @staticmethod
    def decode(data: bytes):
        if data.endswith(bytes(1)):
            # Trim off null byte
            data = data[:-1]
        d = json.loads(data.decode())
        to_ret = messageTypeToConstructor.get(d['type'], Message)()
        to_ret.update(d)
        return to_ret

    def encode(self):
        return json.dumps(self).encode() + bytes(1)


class SuccessMessage(Message):
    TYPE_STR = 'success'


class ErrorMessage(Message):
    TYPE_STR = 'error'
    KEY_CODE = 'code'
    KEY_MESSAGE = 'message'
    ERROR_CODE_UNKNOWN = -1
    ERROR_CODE_UNRECOGNISED_REQUEST = 1

    def __init__(self, code: int = -1, message: str = 'An error occored'):
        super().__init__(type='error')
        self.type = self.TYPE_STR
        self.code = code
        self.message = message

    @property
    def message(self):
        return self[self.KEY_MESSAGE]

    @message.setter
    def message(self, m: str):
        self[self.KEY_MESSAGE] = m

    @property
    def code(self):
        return self[self.KEY_CODE]

    @code.setter
    def code(self, c: int):
        self[self.KEY_CODE] = c


class GetRequest(Message):
    TYPE_STR = 'get'
    KEY_ID = 'id'
    ERROR_NOT_FOUND = 404

    def __init__(self, modid=None):
        super().__init__(self.TYPE_STR)
        self[self.KEY_ID] = modid


class GetResponse(SuccessMessage):
    TYPE_STR = 'mod'
    KEY_MOD_DATA = 'mod'
    DATA_KEY_ID = 'id'
    DATA_KEY_NAME = 'name'
    DATA_KEY_VERSION = 'version'

    def __init__(self, mod_info: ModInfo = None):
        super().__init__()
        self[self.KEY_MOD_DATA] = {self.DATA_KEY_ID: None, self.DATA_KEY_NAME: None, self.DATA_KEY_VERSION: None}
        if mod_info is not None:
            self[self.KEY_MOD_DATA].update(mod_info.to_dict())

    def version(self):
        return self[self.KEY_MOD_DATA][self.DATA_KEY_VERSION]

    @property
    def name(self):
        return self[self.KEY_MOD_DATA][self.DATA_KEY_NAME]

    @property
    def id(self):
        return self[self.KEY_MOD_DATA][self.DATA_KEY_ID]


class ListRequest(Message):
    TYPE_STR = 'list'


class ListResponse(SuccessMessage):
    TYPE_STR = 'modlist'
    KEY_REQUIRED_MODS = 'required'
    KEY_CLIENT_SIDE_MODS = 'optional'
    KEY_SERVER_SIDE_MODS = 'serverside'

    def __init__(self, required={}, clientside=[], serverside=[]):
        super().__init__()
        self[self.KEY_REQUIRED_MODS] = required
        self[self.KEY_CLIENT_SIDE_MODS] = clientside
        self[self.KEY_SERVER_SIDE_MODS] = serverside

    @property
    def clientside_mods(self):
        return self[self.KEY_CLIENT_SIDE_MODS]

    @property
    def required_mods(self):
        return self[self.KEY_REQUIRED_MODS]

    @property
    def serverside_mods(self):
        return self[self.KEY_REQUIRED_MODS]

    @clientside_mods.setter
    def clientside_mods(self, modids: [str]):
        self[self.KEY_CLIENT_SIDE_MODS] = modids

    @serverside_mods.setter
    def serverside_mods(self, modids: [str]):
        self[self.KEY_CLIENT_SIDE_MODS] = modids

    @required_mods.setter
    def required_mods(self, mods: dict):
        self[self.KEY_REQUIRED_MODS] = mods


class SetProfileRequest(Message):
    TYPE_STR = 'set_profile'
    KEY_PASSKEY = 'passkey'
    KEY_CLIENT_MODS = 'mods'
    ERROR_CODE_MISSING_PASSKEY = 100
    ERROR_CODE_INVALID_PASSKEY = 101

    def __init__(self, client_mods={}, passkey=None):
        super().__init__()
        self[self.KEY_PASSKEY] = passkey
        self[self.KEY_CLIENT_MODS] = client_mods


class PingMessage(Message):
    TYPE_STR = 'ping'
    KEY_VERSION = 'version'

    def __init__(self):
        super().__init__()
        self[self.KEY_VERSION] = VERSION


class DownloadRequest(GetRequest):
    TYPE_STR = 'download'


messageTypeToConstructor = {ErrorMessage.TYPE_STR: ErrorMessage,
                            SuccessMessage.TYPE_STR: SuccessMessage,
                            GetRequest.TYPE_STR: GetRequest,
                            GetResponse.TYPE_STR: GetResponse,
                            ListRequest.TYPE_STR: ListRequest,
                            ListResponse.TYPE_STR: ListResponse,
                            DownloadRequest.TYPE_STR: DownloadRequest,
                            SetProfileRequest.TYPE_STR: SetProfileRequest}

