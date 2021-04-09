from serversync.common import *
from serversync import VERSION
from serversync.config_gui import SettingsWidget
from socket import socket, AF_INET, SOCK_STREAM, error, gaierror, timeout
from os import remove
import sys

from threading import Thread

from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QLineEdit, QMessageBox, QGridLayout, QLabel, QListWidget, \
    QListWidgetItem, QCheckBox, QScrollBar, QVBoxLayout, QScrollArea, QHBoxLayout, QTableWidget
from PyQt5.Qt import Qt, QObject, pyqtSignal, QThread, QFont


class Client:
    def __init__(self):
        self.conf = ClientConfig()
        self.on_progress_cb = None

    def _make_sock(self):
        sock = socket(AF_INET, SOCK_STREAM)
        sock.connect(self.conf.server_address)
        return sock

    def ping(self):
        try:
            self.send()
            return True
        except error:
            return False

    def send(self, message: Message):
        sock = self._make_sock()

        sock.send(message.encode())

        ret = b''
        try:
            while True:
                buf = sock.recv(INPUT_BUFFER_SIZE)
                if len(buf) == 0:
                    break
                ret += buf
        except timeout:
            pass
        finally:
            sock.close()

        if len(ret) == 0:
            raise ValueError('Server didnt respond')
        return Message.decode(ret)

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
        info = self.get_mod_info(modid)
        output_filepath = path.join(output_dirpath, info['filename'])
        if path.exists(output_filepath):
            raise FileExistsError(output_filepath)

        modsize = info['size']
        bytes_read = 0
        bytes_remaining = modsize

        with open(output_filepath, 'wb') as file:
            sock = self._make_sock()
            sock.settimeout(1)
            sock.send(DownloadRequest(modid).encode())
            while True:
                try:
                    buf = sock.recv(min(DOWNLOAD_BUFFER_SIZE, bytes_remaining))
                except error:
                    if len(buf) == 0:
                        break
                except:
                    break

                if bytes_read >= modsize:
                    break
                file.write(buf)
                bytes_read += len(buf)
                bytes_remaining -= len(buf)
                if self.on_progress_cb is not None:
                    self.on_progress_cb(bytes_read, modsize)
        if bytes_read != modsize and modsize > 0:
            remove(output_filepath)
            raise ValueError('Incomplete download')
        sock.close()


class ClientGUI(QWidget):
    PROCESS_ADD = 'Add'
    PROCESS_UPDATE = 'Update'
    PROCESS_DEL = 'Delete'

    showMessageBox = pyqtSignal(str, str, bool)
    onLocalDirScanned = pyqtSignal(dict)

    class ModList(QWidget):
        class ModEntry(QWidget):
            def __init__(self, parent_layout: QGridLayout, row_index: int, mod_id: str, modname: str, operation: str, version_str: str, checked=True, on_state_change_cb = None):
                super().__init__()
                self.mod_id = mod_id
                self.row_index = row_index
                self.on_state_change_cb = on_state_change_cb

                self.enabled_cb = QCheckBox()
                self.enabled_cb.setChecked(checked)
                if on_state_change_cb is not None:
                    self.enabled_cb.stateChanged.connect(self._on_state_change)

                parent_layout.addWidget(self.enabled_cb, row_index, 0)

                self.name_label = QLabel(modname)
                parent_layout.addWidget(self.name_label, row_index, 2)

                self.operation = operation
                self.operation_label = QLabel(operation)
                parent_layout.addWidget(self.operation_label, row_index, 1)

                self.ver_label = QLabel(version_str)
                parent_layout.addWidget(self.ver_label, row_index, 3)

            def _on_state_change(self, cb: QCheckBox):
                self.on_state_change_cb(self.mod_id, cb)

        def __init__(self):
            super().__init__()

            self.mod_entries = {}
            self.container = QWidget()

            self.grid = QGridLayout()
            self.clear_table()

            self.grid = QGridLayout()
            self.grid.setColumnStretch(2, 1)
            self.grid.setColumnMinimumWidth(0, 14)
            self.grid.setRowStretch(100, 1)

            self.grid.addWidget(QLabel('Operation'), 0, 1)
            self.grid.addWidget(QLabel('Name'), 0, 2)
            self.grid.addWidget(QLabel('Version'), 0, 3)

            self.container.setLayout(self.grid)

            self.mod_entries = {}
            self.container.setLayout(self.grid)

            scroll = QScrollArea()
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            scroll.setWidgetResizable(True)
            scroll.setWidget(self.container)

            self.layout = QVBoxLayout()
            self.layout.addWidget(scroll)
            scroll.setContentsMargins(0, 0, 0, 0)
            self.setLayout(self.layout)

        def add_mod(self, mod_id: str, name, operation: str, version_str: str, checked: bool = True, on_state_change_cb = None):
            self.mod_entries[mod_id] = self.ModEntry(self.grid, len(self.mod_entries.keys())+1, mod_id, name, operation, version_str, checked, on_state_change_cb=on_state_change_cb)
            self.update()

        def clear_table(self):
            for k in self.mod_entries:
                entry = self.mod_entries[k]
                self.grid.removeWidget(entry.name_label)
                self.grid.removeWidget(entry.ver_label)
                self.grid.removeWidget(entry.enabled_cb)
                self.grid.removeWidget(entry.operation_label)
            self.mod_entries = {}

        def set_progress(self, modid, prog):
            self.mod_entries[modid].operation_label.setText('{}%'.format(prog))

    class ScannerState:
        READY = 0
        RUNNING = 1
        CANCELLED = 2

    def __init__(self):
        super(ClientGUI, self).__init__()

        self.conf = ClientConfig()

        if 'keep' not in self.conf:
            self.conf['keep'] = []

        self.showMessageBox.connect(self.on_show_message_box)
        self.onLocalDirScanned.connect(self._on_local_dir_scanned)

        self.setGeometry(50, 50, 500, 350)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.setWindowTitle('ServerSync | Version {}'.format(VERSION))
        self.show()

        self.upper_text = QLabel()
        self.layout.addWidget(self.upper_text)

        self.modlist_widget = self.ModList()
        self.layout.addWidget(self.modlist_widget)

        self.thread = None
        self.modloader = None

        self.lower_btn_grid = QWidget()
        self.lower_btn_grid_layout = QHBoxLayout()
        self.lower_btn_grid.setLayout(self.lower_btn_grid_layout)

        settings_btn = QPushButton()
        settings_btn.setText('Settings')
        settings_btn.clicked.connect(self._show_settings)
        self.lower_btn_grid_layout.addWidget(settings_btn)

        self.rescan_btn = QPushButton()
        self.rescan_btn.setText('Re-Scan')
        self.rescan_btn.clicked.connect(self._on_rescan_button_pressed)
        self.lower_btn_grid_layout.addWidget(self.rescan_btn)
        self._scanner_state = self.ScannerState.READY

        self.start_btn = QPushButton()
        self.start_btn.setText('Start')
        self.start_btn.clicked.connect(self._start_updating)
        self.start_btn.setEnabled(False)
        self.lower_btn_grid_layout.addWidget(self.start_btn)

        self.layout.addWidget(self.lower_btn_grid)

        self.config_session = None
        self.local_modlist = {}
        self.server_modlist = {}

        self.to_update = []
        self.to_delete = []
        self.to_download = []

        if self.conf.exists():
            self._on_rescan_button_pressed()
        else:
            # First time setup
            self.conf.save()        # Create config file
            self._show_settings()

    def on_show_message_box(self, title, message, error):
        QMessageBox.about(self, title, message)
        if error:
            self.close()

    def _on_checkbox_state_changed(self, mod_id, ch: QCheckBox):
        if ch:
            if mod_id in self.conf['keep']:
                self.conf['keep'].remove(mod_id)
        else:
            if mod_id not in self.conf['keep']:
                self.conf['keep'].append(mod_id)
        self.conf.save()

    def _on_local_dir_scanned(self, mods: dict):
        self.local_modlist = mods

        required_mods = self.server_modlist['required']
        optional_mods = self.server_modlist['optional']

        self.to_update.clear()
        self.to_delete.clear()
        self.to_download.clear()

        for id in mods:
            if id in required_mods:
                if mods[id].version != required_mods[id]['version']:
                    self.to_update.append(id)
            elif id not in optional_mods:
                self.to_delete.append(id)
        for id in required_mods:
            if id not in mods:
                self.to_download.append(id)

        if len(self.to_update) + len(self.to_download) + len(self.to_delete) == 0:
            # QMessageBox.about(self, 'Up to date', 'This mod folder is up to date (scanned {} mods).'.format(len(self.local_modlist)))
            self.upper_text.setText('Scanned! This mod folder is up to date (scanned {} mods)'.format(len(self.local_modlist)))
        else:
            self.upper_text.setText('Scanned {} mods'.format(len(self.local_modlist)))
            to_keep = self.conf['keep']

            for id in self.to_delete:
                mod = self.local_modlist[id]
                self.modlist_widget.add_mod(id, mod.name, ClientGUI.PROCESS_DEL, mod.version, checked=id not in to_keep, on_state_change_cb=self._on_checkbox_state_changed)

            for id in self.to_update:
                mod = self.local_modlist[id]
                new_mod = required_mods[id]
                self.modlist_widget.add_mod(id, mod.name, ClientGUI.PROCESS_UPDATE, '{} -> {}'.format(mod.version, new_mod['version']), checked=id not in to_keep, on_state_change_cb=self._on_checkbox_state_changed)

            for id in self.to_download:
                mod = required_mods[id]
                self.modlist_widget.add_mod(id, mod['name'], ClientGUI.PROCESS_ADD, mod['version'], checked=id not in to_keep, on_state_change_cb=self._on_checkbox_state_changed)

            self.start_btn.setEnabled(True)

    def _show_settings(self):
        self.config_session = SettingsWidget()
        self.config_session.setWindowTitle('Settings')
        self.config_session.show()

    def _on_download_progress(self, id, prog):
        self.modlist_widget.set_progress(id, prog)
        self.upper_text.setText('Running: {} ({}%)'.format(id, prog))

    def _on_download_complete(self):
        self.on_show_message_box('Done', 'Processed {} mods ({} Downloaded, {} Updated, {} Deleted)'.format(
            self._deleted_counter + self._updated_counter + self._downloaded_counter,
            self._downloaded_counter, self._updated_counter, self._deleted_counter
        ), False)
        self.rescan_btn.setEnabled(True)

    def _start_updating(self):
        self.start_btn.setEnabled(False)
        self.rescan_btn.setEnabled(False)

        self._deleted_counter = 0
        self._updated_counter = 0
        self._downloaded_counter = 0

        to_download = []

        for mod_id in self.modlist_widget.mod_entries:
            ele = self.modlist_widget.mod_entries[mod_id]
            if ele.enabled_cb.isChecked():
                self._current_operation_mod_id = mod_id
                if ele.operation == ClientGUI.PROCESS_ADD:
                    to_download.append(mod_id)
                    self._downloaded_counter += 1
                elif ele.operation == ClientGUI.PROCESS_DEL:
                    mod = self.local_modlist[mod_id]
                    remove(mod.filepath)
                    self.modlist_widget.set_progress(mod_id, 100)
                    self._deleted_counter += 1
                elif ele.operation == ClientGUI.PROCESS_UPDATE:
                    mod = self.local_modlist[mod_id]
                    remove(mod.filepath)
                    to_download.append(mod_id)
                    self._updated_counter += 1

        self.thread = QThread()
        self.modloader = ModDownloader(to_download)
        self.modloader.moveToThread(self.thread)
        self.thread.started.connect(self.modloader.run)
        self.modloader.finished.connect(self.thread.quit)
        self.modloader.finished.connect(self.modloader.deleteLater)
        self.modloader.finished.connect(self.thread.deleteLater)
        self.modloader.finished.connect(self._on_download_complete)
        # self.modloader.finished.connect(self._on_modlist_load)
        self.modloader.progress.connect(self._on_download_progress)
        self.thread.start()

    def _on_rescan_button_pressed(self):
        if self._scanner_state == self.ScannerState.RUNNING:
            # Cancel scan
            # self.modloader.running = False
            self._scanner_state = self.ScannerState.CANCELLED
            self.modloader.cancelScanSignal.emit()
        else:
            self.modlist_widget.clear_table()
            client = Client()
            # self.rescan_btn.setEnabled(False)
            self.rescan_btn.setText('Cancel')
            self._scanner_state = self.ScannerState.RUNNING
            try:
                self.server_modlist = client.get_server_mod_list()

                self.thread = QThread()
                self.modloader = ModLoader(self)
                self.modloader.moveToThread(self.thread)
                self.thread.started.connect(self.modloader.run)
                self.modloader.onLocalDirScanned.connect(self.onLocalDirScanned)
                self.modloader.onErrorSignal.connect(self.showMessageBox)
                self.modloader.finished.connect(self.thread.quit)
                self.modloader.finished.connect(self.thread.deleteLater)
                self.modloader.finished.connect(self._on_modloader_finish)
                self.modloader.progress.connect(self.report_progress)
                self.thread.start()
            except ConnectionRefusedError as e:
                self.rescan_btn.setText('Re-Scan')
                self.rescan_btn.setEnabled(True)
                self.on_show_message_box('Unable to connect to server', 'Unable to connect to server at {}:{}\n{}'.format(client.conf.server_ip, client.conf.server_port, e), False)

    def report_progress(self, prog):
        self.upper_text.setText('Scanning... {}%'.format(prog))

    def _on_modloader_finish(self):
        if self._scanner_state == self.ScannerState.RUNNING:
            self._scanner_state = self.ScannerState.READY
        else:
            self.upper_text.setText('Scan cancelled')

        self.rescan_btn.setText('Re-Scan')
        self.modloader.deleteLater()

    def set_message(self, msg: str):
        self.message.setText(msg)


class ModDownloader(QObject):
    finished = pyqtSignal()
    progress = pyqtSignal(str, int)

    def __init__(self, mod_ids):
        super().__init__()
        self.mod_ids = mod_ids
        self.cur_id = None

    def run(self) -> None:
        client = Client()
        client.on_progress_cb = self._on_progress_2
        for mod_id in self.mod_ids:
            self.cur_id = mod_id
            try:
                client.download_file(mod_id, '.')
            except error as e:
                self.parent.showMessageBox.emit('Failed to connect to server', 'Failed to connect to server at {}:{}\n {}'.format(
                    client.conf.server_ip, client.conf.server_port, e), False)
                self.finished.emit()
                return

        self.finished.emit()

    def _on_progress_2(self, cur, total):
        self._on_progress(int(100*cur/total))

    def _on_progress(self, prog):
        self.progress.emit(self.cur_id, prog)


class ModLoader(QObject):
    # Signal outputs
    finished = pyqtSignal()
    onLocalDirScanned = pyqtSignal(dict)
    progress = pyqtSignal(int)
    onErrorSignal = pyqtSignal(str, str, bool)

    # Signal input
    cancelScanSignal = pyqtSignal()

    def __init__(self, client_gui: ClientGUI):
        super().__init__()
        self.parent = client_gui
        self.cancelScanSignal.connect(self._on_cancel_signal)
        self.running = False

    def _on_cancel_signal(self):
        print('Cancel sign')
        self.running = False

    def run(self) -> None:
        self.running = True
        client = Client()
        # self.text.setText('Pulling mod config from server...')
        try:
            server_mods = client.get_server_mod_list()
        except error as e:
            self.onErrorSignal.emit('Failed to connect to server', 'Failed to connect to server at {}:{}\n {}'.format(
                client.conf.server_ip, client.conf.server_port, e), False)
            self.finished.emit()
            return

        self.progress.emit(0)
        print('Compiling list of mods...   0%', end='', flush=True)
        to_ret = {}
        files = [f for f in listdir('.') if f.endswith('.jar')]
        nfiles = len(files)
        for i in range(nfiles):
            if not self.running:
                break
            f = files[i]
            try:
                m = ModInfo(f)
                to_ret[m.id] = m
            except KeyError as e:
                print('[WN] {}: {}'.format(f, e))
            except zipfile.BadZipFile as e:
                print('[WN]: {}. Deleted.'.format(e))

            prog = int(100 * (i + 1) / nfiles)
            self.progress.emit(prog)

        if self.running:
            # No interrupt, scan complete

            self.onLocalDirScanned.emit(to_ret)

        self.finished.emit()

