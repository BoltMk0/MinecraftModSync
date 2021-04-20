
from os import getcwd
import sys
from serversync.common import *

from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QLineEdit, QMessageBox, QGridLayout, QLabel, QCheckBox
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
            QMessageBox.about(self, 'Config saved', 'Config saved')
            self._reset()

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

    def initUI(self):
        grid = QGridLayout()
        self.setLayout(grid)
        self.setWindowTitle('ServerSync Settings')

        self.ip_option = self.Option(grid, 'Server IP', 'localhost', 0)
        self.port_option = self.Option(grid, 'Server Port', str(DEFAULT_SERVER_PORT), 1)

        self.enable_redirects = QCheckBox(self)
        grid.addWidget(QLabel("Allow Redirects"), 3, 0)
        grid.addWidget(self.enable_redirects, 3, 1)

        reset_btn = QPushButton()
        reset_btn.setText('Reset')
        reset_btn.clicked.connect(self._reset)
        grid.addWidget(reset_btn, 4, 0)

        test_btn = QPushButton()
        test_btn.setText('Test')
        test_btn.clicked.connect(self._test)
        grid.addWidget(test_btn, 4, 1)

        save_btn = QPushButton()
        save_btn.setText('Save')
        save_btn.clicked.connect(self._save)
        grid.addWidget(save_btn, 4, 2)

        self._reset()
        self.show()


def config_editor_session():
    app = QApplication(sys.argv)
    ex = SettingsWidget()
    sys.exit(app.exec_())

if __name__ == '__main__':
    config_editor_session()