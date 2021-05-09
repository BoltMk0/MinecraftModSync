
from os import getcwd
import sys
from serversync.common import *
from serversync.client import *

from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QLineEdit, QMessageBox, QGridLayout, QLabel, QCheckBox, QVBoxLayout
import sys

from socket import socket, SOCK_STREAM, AF_INET, error, gethostbyname, gaierror, timeout


def install_context_menu():
    import winreg
    key_path = r"Directory\\Background\\shell\\ServerSync"
    key = winreg.CreateKeyEx(winreg.HKEY_CLASSES_ROOT, key_path)
    key2 = winreg.CreateKeyEx(key, r"command")

    cwd = getcwd()

    python_exe = sys.executable
    pythonw_exe_parts = python_exe.split('\\')
    pythonw_exe_parts[-1] = 'pythonw.exe'
    pythonw_exe = '\\'.join(pythonw_exe_parts)

    winreg.SetValue(key, '', winreg.REG_SZ, '&Run ServerSync')
    winreg.SetValue(key2, '', winreg.REG_SZ, '{} -m serversync'.format(pythonw_exe if path.exists(pythonw_exe) else python_exe))


def uninstall_context_menu():
    import winreg
    key_path = r"Directory\\Background\\shell\\ServerSync"
    key = winreg.CreateKeyEx(winreg.HKEY_CLASSES_ROOT, key_path)
    key2 = winreg.CreateKeyEx(key, r"command")
    print('  Removing command subkey... ', end='')
    winreg.DeleteKey(key2, '')
    print('[OK]')
    print('  Removing ServerSync key... ', end='')
    winreg.DeleteKey(key, '')
    print('[OK]')


class SettingsWidget(QWidget):

    class Option:
        def __init__(self, parent_layout: QGridLayout, name, default, row: int):
            self.name = name
            self.default = default

            self.label = QLabel()
            self.label.setText(self.name)
            self.input = QLineEdit()
            self.input.setText(self.default)
            self.default_btn = QPushButton()
            self.default_btn.setText('Default')
            self.default_btn.clicked.connect(self._reset)

            parent_layout.addWidget(self.label, row, 0)
            parent_layout.addWidget(self.input, row, 1)
            parent_layout.addWidget(self.default_btn, row, 2)

        def _reset(self):
            self.input.setText(self.default)

    def __init__(self):
        super().__init__()
        self.initUI()
        self._set_profile_box = None

    def _reset(self):
        conf = ServerSyncConfig()
        self.ip_option.input.setText(conf.server_ip)
        self.port_option.input.setText(str(conf.server_port))
        self.enable_redirects.setChecked(conf.allow_redirects)

    def _save(self):
        try:
            conf = ServerSyncConfig()
            conf.server_port = int(self.port_option.input.text())
            conf.server_ip = self.ip_option.input.text()
            conf.allow_redirects = self.enable_redirects.isChecked()

            try:
                gethostbyname(conf.server_ip)
            except gaierror:
                QMessageBox.about(self, "Invalid hostname", 'WARNING: Unable to resolve hostname: "{}"'.format(conf.server_ip))
            conf.save()
            QMessageBox.about(self, 'Config saved', 'Config saved to {}'.format(path.abspath(conf.filepath)))
            self.close()

        except ValueError:
            QMessageBox.about(self, "Invalid port value", 'Invalid port value "{}". Must be an integer.'.format(self.port_option.input.text()))

    def _test(self):
        sock = socket(AF_INET, SOCK_STREAM)
        sock.settimeout(1)
        try:
            hostname = self.ip_option.input.text()
            ret = gethostbyname(hostname)
            sock.connect((hostname, int(self.port_option.input.text())))
            try:
                sock.send(PingMessage().encode())
                msg = Message.decode(sock.recv(MESSAGE_BUFFER_SIZE))

                if msg.type == PingMessage.TYPE_STR:
                    QMessageBox.about(self, 'Success', 'Successfully connected to ServerSync {} server'.format(
                        msg[PingMessage.KEY_VERSION]))
                else:
                    QMessageBox.about(self, 'Failed', 'Server failed to respond correctly.')

            except timeout:
                # Possibly old server, try legacy ping:
                sock.send(b'ping')
                ret = sock.recv(MESSAGE_BUFFER_SIZE)

                if ret == b'pong':
                    QMessageBox.about(self, 'Success', 'Successfully connected to legacy (0.x) ServerSync server'.format(
                        msg[PingMessage.KEY_VERSION]))
                else:
                    QMessageBox.about(self, 'Failed', 'Server failed to respond correctly.')

        except gaierror:
            QMessageBox.about(self, "Unable to connect to server", 'Unable to resolve hostname: "{}"'.format(hostname))
        except error as e:
            QMessageBox.about(self, "Unable to connect to server", str(e))
        except ValueError:
            QMessageBox.about(self, "Invalid port value", 'Invalid port value "{}". Must be an integer.'.format(self.port_option.input.text()))
        finally:
            sock.close()

    def _set_profile_pressed(self):
        if self._set_profile_box is not None:
            self._set_profile_box.close()
        self._set_profile_box = SubmitClientConfigPopup()

    def _revert_profile_pressed(self):
        if self._set_profile_box is not None:
            self._set_profile_box.close()
        self._set_profile_box = SubmitClientConfigPopup(revert_mode=True)

    def initUI(self):
        grid = QGridLayout()
        self.setLayout(grid)
        self.setWindowTitle('ServerSync Settings')

        self.ip_option = self.Option(grid, 'Server IP', 'localhost', 0)
        self.port_option = self.Option(grid, 'Server Port', str(DEFAULT_SERVER_PORT), 1)

        self.enable_redirects = QCheckBox(self)
        grid.addWidget(QLabel("Allow Redirects"), 3, 0)
        grid.addWidget(self.enable_redirects, 3, 1)

        grid.addWidget(QLabel('(Admin) Client Profile'), 4, 0)
        set_profile_btn = QPushButton('Set Profile', self)
        set_profile_btn.clicked.connect(self._set_profile_pressed)
        revert_profile_btn = QPushButton('Revert', self)
        revert_profile_btn.clicked.connect(self._revert_profile_pressed)
        grid.addWidget(set_profile_btn, 4, 1)
        grid.addWidget(revert_profile_btn, 4, 2)

        reset_btn = QPushButton()
        reset_btn.setText('Reset')
        reset_btn.clicked.connect(self._reset)
        grid.addWidget(reset_btn, 5, 0)

        test_btn = QPushButton()
        test_btn.setText('Test')
        test_btn.clicked.connect(self._test)
        grid.addWidget(test_btn, 5, 1)

        save_btn = QPushButton()
        save_btn.setText('Save')
        save_btn.clicked.connect(self._save)
        grid.addWidget(save_btn, 5, 2)

        self._reset()
        self.show()


class SubmitClientConfigPopup(QWidget):

    def __init__(self, revert_mode=False):
        super().__init__()
        self.initUI()
        self.setFixedWidth(300)
        self._revert_mode = revert_mode

    def _submit(self):
        self.submit_button.setEnabled(False)
        self.input.setEnabled(False)
        try:
            self.set_message('Building profile...')
            modlist = list_mods_in_dir()
            profile = {mid: modlist[mid].to_dict() for mid in modlist}
            cli = Client()
            self.set_message('Connecting to server ({}:{})...'.format(cli.conf.server_ip, cli.conf.server_port))
            try:
                cli.connect()
            except Exception as e:
                QMessageBox.about(self, 'Error', 'Unable to connect to server: {}'.format(str(e)))
                return
            try:
                if self._revert_mode:
                    self.set_message('Reverting client profile...')
                    ret = cli.send(RevertProfileRequest(passkey=self.input.text()))
                    if ret.TYPE_STR != SuccessMessage.TYPE_STR:
                        QMessageBox.about(self, 'Error: unexpected response', 'Unexpected response from server:\n{}'.format(ret))
                    else:
                        # Now pull new modlist from server
                        response = cli.get_server_mod_list()
                        if response.type == ErrorMessage.type:
                            QMessageBox.about(self, 'Warning',
                                              'Profile was reverted, but the client was unable to pull the modlist from the server.')
                        elif response.type != ListResponse.TYPE_STR:
                            QMessageBox.about(self, 'Warning',
                                              'Profile was reverted, but the client received an unexpected response to modlist:\n{}'.format(
                                                  str(response)))
                        else:
                            server_modlist = response[ListResponse.KEY_REQUIRED_MODS]
                            optional = response[ListResponse.KEY_CLIENT_SIDE_MODS]
                            server_side = response[ListResponse.KEY_SERVER_SIDE_MODS]

                            QMessageBox.about(self, 'Success!', 'Successfully reverted client profile\n'
                                                                '   {} Required mods\n'
                                                                '   {} Client-side mods\n'
                                                                '   {} Server-side mods'.format(len(server_modlist),
                                                                                                len(optional),
                                                                                                len(server_side)))
                else:
                    self.set_message('Uploading profile to server...')
                    to_send = SetProfileRequest(profile, passkey=self.input.text())
                    ret = cli.send(to_send)

                    if ret.type == ErrorMessage.TYPE_STR:
                        QMessageBox.about(self, 'Error', 'An error occored when setting profile:\n({}) {}: {}'.format(
                            ret[ErrorMessage.KEY_CODE], ret[ErrorMessage.KEY_TYPE], ret[ErrorMessage.KEY_MESSAGE]))
                        return
                    elif ret['type'] == SuccessMessage.TYPE_STR:
                        QMessageBox.about(self, 'Success!', 'Successfully updated server profile!')
                    elif ret['type'] == DownloadRequest.TYPE_STR:
                        # Server wants to download copies of client side mods first.
                        while True:
                            self.set_message('Uploading {} to server...'.format(ret[DownloadRequest.KEY_ID]))
                            if ret['type'] == DownloadRequest.TYPE_STR:
                                mod_id = ret[DownloadRequest.KEY_ID]
                                mod = modlist[mod_id]
                                print('Uploading {}... '.format(mod.name), end='')
                                with open(mod.filepath, 'rb') as file:
                                    data = file.read()
                                ret = Message.decode(cli.send_raw(data))
                                print('[OK] Sent')
                            elif ret['type'] == SuccessMessage.TYPE_STR:
                                break
                            else:
                                raise UnexpectedResponseError(str(ret))

                    # Now pull new modlist from server
                    response = cli.get_server_mod_list()
                    if response.type == ErrorMessage.type:
                        QMessageBox.about(self, 'Warning', 'Profile was set, but the client was unable to pull the modlist from the server.')
                    elif response.type != ListResponse.TYPE_STR:
                        QMessageBox.about(self, 'Warning', 'Profile was set, but the client received an unexpected response to modlist:\n{}'.format(str(response)))
                    else:
                        server_modlist = response[ListResponse.KEY_REQUIRED_MODS]
                        optional = response[ListResponse.KEY_CLIENT_SIDE_MODS]
                        server_side = response[ListResponse.KEY_SERVER_SIDE_MODS]

                        QMessageBox.about(self, 'Success!', 'Successfully set client profile\n'
                                                            '   {} Required mods\n'
                                                            '   {} Client-side mods\n'
                                                            '   {} Server-side mods'.format(len(server_modlist), len(optional), len(server_side)))

            except Exception as e:
                QMessageBox.about(self, 'Error', 'An unexpected error occured during upload:\n{}'.format(str(e)))
                return
        except:
            raise
        finally:
            self.submit_button.setEnabled(True)
            self.input.setEnabled(True)
            self.set_message('Enter passkey (if required)')

    def set_message(self, msg: str):
        self.label.setText(msg)

    def initUI(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        self.setWindowTitle('Enter Passkey')

        self.label = QLabel('Enter passkey (if required)', self)
        self.input = QLineEdit(self)
        self.submit_button = QPushButton('Submit', self)

        layout.addWidget(self.label)
        layout.addWidget(self.input)
        layout.addWidget(self.submit_button)

        self.submit_button.pressed.connect(self._submit)

        self.show()


def config_editor_session():
    app = QApplication(sys.argv)
    ex = SettingsWidget()
    sys.exit(app.exec_())


if __name__ == '__main__':
    config_editor_session()