"""
Chat2DB Connector
=================
GUI (PySide6) + SSH tunnel (paramiko) + auto-launch browser.

Build:
    pyinstaller --onefile --windowed --name Chat2DBConnector chat2db-connector.py
"""
import sys
import os
import json
import socket
import select
import webbrowser
from pathlib import Path

import paramiko
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QTextCursor, QColor, QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QLineEdit, QPushButton, QCheckBox, QPlainTextEdit,
    QFileDialog, QMessageBox, QStatusBar,
)

APP_NAME = "Chat2DB Connector"
CONFIG_DIR = Path.home() / ".chat2db-connector"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "ssh_host": "192.168.0.197",
    "ssh_port": 22,
    "ssh_user": "vscode",
    "key_file": str(Path.home() / ".ssh" / "id_ed25519"),
    "local_port": 10825,
    "remote_host": "127.0.0.1",
    "remote_port": 10825,
    "auto_open_browser": True,
    "url_path": "",
}


# ---------------------------------------------------------------------------
#  SSH port forwarding
# ---------------------------------------------------------------------------
class SSHTunnel:
    """Listen on a local port, forward each connection through SSH."""

    def __init__(self, log_cb):
        # log_cb: callable(str) -> None (will be called from worker thread)
        self._log = log_cb
        self.client = None
        self.transport = None
        self.server_sock = None
        self._running = False
        self._accept_thread = None

    def start(self, host, port, user, key_file,
              local_port, remote_host, remote_port):
        if self._running:
            raise RuntimeError("tunnel already running")

        self._log(f"[1/3] Connecting SSH {user}@{host}:{port} ...")
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            self.client.connect(
                hostname=host,
                port=port,
                username=user,
                key_filename=key_file,
                look_for_keys=False,
                allow_agent=False,
                timeout=10,
            )
        except paramiko.AuthenticationException:
            self.cleanup()
            raise RuntimeError("Auth failed: check private key vs server's authorized_keys")
        except paramiko.SSHException as e:
            self.cleanup()
            raise RuntimeError(f"SSH error: {e}")
        except Exception as e:
            self.cleanup()
            raise RuntimeError(f"Connect failed: {e}")

        self.transport = self.client.get_transport()
        if self.transport is None or not self.transport.is_active():
            self.cleanup()
            raise RuntimeError("SSH transport unavailable")

        self._log("[2/3] SSH connected, opening local port forward ...")
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.server_sock.bind(("127.0.0.1", local_port))
        except OSError:
            self.cleanup()
            raise RuntimeError(f"Local port {local_port} already in use")

        self.server_sock.listen(64)
        self.server_sock.settimeout(0.5)
        self._running = True
        self._accept_thread = threading.Thread(
            target=self._accept_loop, args=(remote_host, remote_port), daemon=True
        )
        self._accept_thread.start()
        self._log(f"[3/3] Tunnel ready -> http://127.0.0.1:{local_port}")
        return True

    def _accept_loop(self, remote_host, remote_port):
        while self._running:
            try:
                rlist, _, _ = select.select([self.server_sock], [], [], 0.5)
                if not rlist:
                    continue
                client_sock, addr = self.server_sock.accept()
            except (OSError, socket.error):
                break
            try:
                channel = self.transport.open_channel(
                    "direct-tcpip", (remote_host, remote_port), addr,
                )
            except Exception as e:
                self._log(f"[warn] open channel failed: {e}")
                client_sock.close()
                continue
            threading.Thread(
                target=self._pump, args=(client_sock, channel), daemon=True
            ).start()

    @staticmethod
    def _pump(src, dst):
        try:
            while True:
                r, _, _ = select.select([src, dst], [], [], 1.0)
                if not r:
                    continue
                for sock in r:
                    try:
                        data = sock.recv(8192)
                    except OSError:
                        data = b""
                    if not data:
                        raise EOFError
                    other = dst if sock is src else src
                    try:
                        other.sendall(data)
                    except OSError:
                        raise EOFError
        except (EOFError, OSError, Exception):
            pass
        finally:
            for s in (src, dst):
                try:
                    s.close()
                except Exception:
                    pass

    def stop(self):
        if not self._running:
            return
        self._running = False
        self.cleanup()

    def cleanup(self):
        if self.server_sock:
            try:
                self.server_sock.close()
            except Exception:
                pass
            self.server_sock = None
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
            self.client = None
            self.transport = None


# Late import so the docstring's import block reads cleanly above
import threading


# ---------------------------------------------------------------------------
#  Worker thread (QThread) that runs the SSH connect without blocking UI
# ---------------------------------------------------------------------------
class ConnectWorker(QThread):
    log = Signal(str, str)      # message, level ("info" / "ok" / "err")
    connected = Signal(dict)    # config
    failed = Signal()

    def __init__(self, tunnel, cfg, parent=None):
        super().__init__(parent)
        self.tunnel = tunnel
        self.cfg = cfg

    def run(self):
        try:
            self.tunnel.start(
                self.cfg["ssh_host"], self.cfg["ssh_port"], self.cfg["ssh_user"],
                self.cfg["key_file"],
                self.cfg["local_port"], self.cfg["remote_host"], self.cfg["remote_port"],
            )
        except Exception as e:
            self.log.emit(f"X {e}", "err")
            self.failed.emit()
            return
        self.connected.emit(self.cfg)


# ---------------------------------------------------------------------------
#  Main window
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = self.load_config()
        self.tunnel = SSHTunnel(log_cb=self._log_from_worker)
        self.worker = None

        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(560, 520)
        self._build_ui()
        self._populate_fields()

    # ---- config ----
    def load_config(self):
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                return {**DEFAULT_CONFIG, **cfg}
        except Exception as e:
            print(f"[warn] load config failed: {e}")
        return DEFAULT_CONFIG.copy()

    def save_config(self):
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            QMessageBox.critical(self, "Save failed", str(e))

    # ---- UI ----
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 6)
        root.setSpacing(8)

        # --- SSH group ---
        ssh_box = QGroupBox("SSH Server")
        ssh = QGridLayout(ssh_box)
        ssh.setContentsMargins(10, 12, 10, 10)
        ssh.setHorizontalSpacing(8)
        ssh.setVerticalSpacing(6)

        ssh.addWidget(QLabel("Host:"), 0, 0, Qt.AlignRight)
        self.edit_host = QLineEdit()
        ssh.addWidget(self.edit_host, 0, 1)

        ssh.addWidget(QLabel("Port:"), 0, 2, Qt.AlignRight)
        self.edit_ssh_port = QLineEdit()
        self.edit_ssh_port.setMaximumWidth(70)
        ssh.addWidget(self.edit_ssh_port, 0, 3)

        ssh.addWidget(QLabel("User:"), 1, 0, Qt.AlignRight)
        self.edit_user = QLineEdit()
        self.edit_user.setMaximumWidth(180)
        ssh.addWidget(self.edit_user, 1, 1, 1, 3)

        ssh.addWidget(QLabel("Private key:"), 2, 0, Qt.AlignRight)
        self.edit_key = QLineEdit()
        ssh.addWidget(self.edit_key, 2, 1, 1, 2)
        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.clicked.connect(self._choose_key)
        ssh.addWidget(self.btn_browse, 2, 3)

        root.addWidget(ssh_box)

        # --- Port mapping group ---
        port_box = QGroupBox("Port Mapping   (local  ->  remote)")
        port = QGridLayout(port_box)
        port.setContentsMargins(10, 12, 10, 10)
        port.setHorizontalSpacing(8)
        port.setVerticalSpacing(6)

        port.addWidget(QLabel("Local port:"), 0, 0, Qt.AlignRight)
        self.edit_local_port = QLineEdit()
        self.edit_local_port.setMaximumWidth(70)
        port.addWidget(self.edit_local_port, 0, 1)

        port.addWidget(QLabel("Remote host:"), 0, 2, Qt.AlignRight)
        self.edit_remote_host = QLineEdit()
        self.edit_remote_host.setMaximumWidth(140)
        port.addWidget(self.edit_remote_host, 0, 3)

        port.addWidget(QLabel("Remote port:"), 0, 4, Qt.AlignRight)
        self.edit_remote_port = QLineEdit()
        self.edit_remote_port.setMaximumWidth(70)
        port.addWidget(self.edit_remote_port, 0, 5)

        port.addWidget(QLabel("URL path:"), 1, 0, Qt.AlignRight)
        self.edit_url_path = QLineEdit()
        self.edit_url_path.setPlaceholderText("optional, e.g. /chat2db")
        port.addWidget(self.edit_url_path, 1, 1, 1, 4)
        port.addWidget(QLabel("(optional)"), 1, 5)

        root.addWidget(port_box)

        # --- Log group ---
        log_box = QGroupBox("Log")
        log_layout = QVBoxLayout(log_box)
        log_layout.setContentsMargins(8, 12, 8, 8)
        self.txt = QPlainTextEdit()
        self.txt.setReadOnly(True)
        self.txt.setMaximumBlockCount(1000)
        self.txt.setFont(QFont("Consolas", 9))
        self.txt.setStyleSheet(
            "QPlainTextEdit { background:#1e1e1e; color:#d4d4d4; border:none; }"
        )
        log_layout.addWidget(self.txt)
        root.addWidget(log_box, 1)

        # --- Options row ---
        opt_row = QHBoxLayout()
        self.chk_auto = QCheckBox("Auto-open browser when connected")
        opt_row.addWidget(self.chk_auto)
        opt_row.addStretch(1)
        self.btn_open = QPushButton("Open browser")
        self.btn_open.clicked.connect(self._open_browser)
        opt_row.addWidget(self.btn_open)
        self.btn_save = QPushButton("Save config")
        self.btn_save.clicked.connect(self._on_save)
        opt_row.addWidget(self.btn_save)
        root.addLayout(opt_row)

        # --- Action buttons + state ---
        act_row = QHBoxLayout()
        self.btn_conn = QPushButton("Connect")
        self.btn_conn.setMinimumHeight(40)
        self.btn_conn.clicked.connect(self._on_connect)
        act_row.addWidget(self.btn_conn)
        self.btn_disc = QPushButton("Disconnect")
        self.btn_disc.setMinimumHeight(40)
        self.btn_disc.setEnabled(False)
        self.btn_disc.clicked.connect(self._on_disconnect)
        act_row.addWidget(self.btn_disc)
        act_row.addStretch(1)
        self.lbl_state = QLabel("  Not connected  ")
        self.lbl_state.setStyleSheet("color: gray;")
        act_row.addWidget(self.lbl_state)
        root.addLayout(act_row)

        # Status bar
        self.setStatusBar(QStatusBar())

    def _populate_fields(self):
        self.edit_host.setText(self.config.get("ssh_host", ""))
        self.edit_ssh_port.setText(str(self.config.get("ssh_port", 22)))
        self.edit_user.setText(self.config.get("ssh_user", ""))
        self.edit_key.setText(self.config.get("key_file", ""))
        self.edit_local_port.setText(str(self.config.get("local_port", 10825)))
        self.edit_remote_host.setText(self.config.get("remote_host", "127.0.0.1"))
        self.edit_remote_port.setText(str(self.config.get("remote_port", 10825)))
        self.edit_url_path.setText(self.config.get("url_path", ""))
        self.chk_auto.setChecked(self.config.get("auto_open_browser", True))

    def _collect(self):
        try:
            cfg = {
                "ssh_host": self.edit_host.text().strip(),
                "ssh_port": int(self.edit_ssh_port.text().strip() or "22"),
                "ssh_user": self.edit_user.text().strip(),
                "key_file": self.edit_key.text().strip(),
                "local_port": int(self.edit_local_port.text().strip() or "10825"),
                "remote_host": self.edit_remote_host.text().strip() or "127.0.0.1",
                "remote_port": int(self.edit_remote_port.text().strip() or "10825"),
                "url_path": self.edit_url_path.text().strip(),
                "auto_open_browser": self.chk_auto.isChecked(),
            }
        except ValueError:
            QMessageBox.critical(self, "Bad input", "Ports must be numbers")
            return None
        if not cfg["ssh_host"] or not cfg["ssh_user"] or not cfg["key_file"]:
            QMessageBox.critical(self, "Bad input",
                                 "Host, user and private key are required")
            return None
        return cfg

    def _choose_key(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose SSH private key",
            str(Path.home() / ".ssh"),
            "All files (*);;PEM (*.pem);;Key (*.key)",
        )
        if path:
            self.edit_key.setText(path)

    # ---- logging (thread-safe) ----
    def _log_from_worker(self, msg):
        # called from worker thread; marshal to GUI thread
        self._post_log(msg, "info")

    def _post_log(self, msg, level="info"):
        # ensure runs on GUI thread
        QThread.currentThread  # noqa  (sanity)
        # Use invokeMethod to be safe even if called from worker:
        from PySide6.QtCore import QMetaObject, Qt as _Qt, Q_ARG
        QMetaObject.invokeMethod(
            self, "_append_log", _Qt.QueuedConnection,
            Q_ARG(str, msg), Q_ARG(str, level),
        )

    def _append_log(self, msg, level):
        color = {
            "ok":   QColor("#4ec9b0"),
            "err":  QColor("#f48771"),
            "info": QColor("#9cdcfe"),
        }.get(level, QColor("#d4d4d4"))
        cursor = self.txt.textCursor()
        cursor.movePosition(QTextCursor.End)
        fmt = cursor.charFormat()
        fmt.setForeground(color)
        cursor.setCharFormat(fmt)
        cursor.insertText(msg + "\n")
        self.txt.setTextCursor(cursor)
        self.txt.ensureCursorVisible()

    def _log(self, msg, level="info"):
        self._append_log(msg, level)

    # ---- actions ----
    def _on_save(self):
        cfg = self._collect()
        if not cfg:
            return
        self.config = cfg
        self.save_config()
        self._log(f"OK Config saved to {CONFIG_FILE}", "ok")

    def _on_connect(self):
        if self.tunnel._running:
            return
        cfg = self._collect()
        if not cfg:
            return
        if not os.path.isfile(cfg["key_file"]):
            QMessageBox.critical(self, "Key file not found", cfg["key_file"])
            return
        self.config = cfg
        self.save_config()

        self.btn_conn.setEnabled(False)
        self.btn_disc.setEnabled(True)
        self.lbl_state.setText("  Connecting...  ")
        self.lbl_state.setStyleSheet("color: orange;")
        self._log("---------- Connecting ----------", "info")

        self.worker = ConnectWorker(self.tunnel, cfg, parent=self)
        self.worker.log.connect(self._append_log)
        self.worker.connected.connect(self._on_connected)
        self.worker.failed.connect(self._on_failed)
        self.worker.finished.connect(self._worker_finished)
        self.worker.start()

    def _on_connected(self, cfg):
        self.lbl_state.setText("  Connected  ")
        self.lbl_state.setStyleSheet("color: #2ea043; font-weight: bold;")
        url = f"http://127.0.0.1:{cfg['local_port']}{cfg.get('url_path', '')}"
        self._log(f"OK Open: {url}", "ok")
        if cfg["auto_open_browser"]:
            try:
                webbrowser.open(url)
            except Exception as e:
                self._log(f"[warn] open browser failed: {e}", "err")

    def _on_failed(self):
        self.btn_conn.setEnabled(True)
        self.btn_disc.setEnabled(False)
        self.lbl_state.setText("  Not connected  ")
        self.lbl_state.setStyleSheet("color: gray;")

    def _worker_finished(self):
        self.worker = None

    def _on_disconnect(self):
        self.tunnel.stop()
        self.btn_conn.setEnabled(True)
        self.btn_disc.setEnabled(False)
        self.lbl_state.setText("  Not connected  ")
        self.lbl_state.setStyleSheet("color: gray;")
        self._log("X Disconnected", "err")

    def _open_browser(self):
        cfg = self._collect()
        if cfg:
            url = f"http://127.0.0.1:{cfg['local_port']}{cfg.get('url_path', '')}"
            webbrowser.open(url)

    def closeEvent(self, event):
        if self.tunnel._running:
            ans = QMessageBox.question(
                self, "Quit", "Tunnel is still running. Quit anyway?"
            )
            if ans != QMessageBox.Yes:
                event.ignore()
                return
        self.tunnel.stop()
        if self.worker and self.worker.isRunning():
            self.worker.wait(2000)
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
