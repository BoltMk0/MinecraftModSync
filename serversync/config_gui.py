
from os import getcwd
import sys
from serversync.common import *

from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QLineEdit, QMessageBox, QGridLayout, QLabel
import sys

from socket import socket, SOCK_STREAM, AF_INET, error, gethostbyname, gaierror


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
        conf = ClientConfig()
        self.ip_option.input.setText(conf.server_ip)
        self.port_option.input.setText(str(conf.server_port))

    def _save(self):
        try:
            conf = ClientConfig()
            conf.server_port = int(self.port_option.input.text())
            conf.server_ip = self.ip_option.input.text()
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
        try:
            hostname = self.ip_option.input.text()
            ret = gethostbyname(hostname)
            sock.connect((hostname, int(self.port_option.input.text())))
            sock.send('ping'.encode())
            if sock.recv(INPUT_BUFFER_SIZE).decode() == 'pong':
                QMessageBox.about(self, 'Success', 'Successfully connected to ServerSync instance')
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

        self.ip_option = self.Option(grid, 'Server IP', 'marcobolt.com', 0)
        self.port_option = self.Option(grid, 'Server Port', str(DEFAULT_SERVER_PORT), 1)

        reset_btn = QPushButton()
        reset_btn.setText('Reset')
        reset_btn.clicked.connect(self._reset)
        grid.addWidget(reset_btn, 3, 0)

        test_btn = QPushButton()
        test_btn.setText('Test')
        test_btn.clicked.connect(self._test)
        grid.addWidget(test_btn, 3, 1)

        save_btn = QPushButton()
        save_btn.setText('Save')
        save_btn.clicked.connect(self._save)
        grid.addWidget(save_btn, 3, 2)

        self._reset()
        self.show()


def config_editor_session():
    app = QApplication(sys.argv)
    ex = SettingsWidget()
    sys.exit(app.exec_())

if __name__ == '__main__':
    config_editor_session()