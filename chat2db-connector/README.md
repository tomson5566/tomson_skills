# Chat2DB Connector

A Windows desktop tool that:
1. Opens an SSH tunnel to a remote server
2. Forwards `127.0.0.1:10825` -> remote `127.0.0.1:10825`
3. Auto-opens your browser to Chat2DB

GUI built with **PySide6** (Qt), SSH layer with **paramiko**. Tested on Windows 10 / 11.

---

## Project layout

```
chat2db-connector/
├── chat2db-connector.py     # main program (GUI + tunnel)
├── build.bat                # one-click build script
├── requirements.txt         # dependencies
├── .venv/                   # auto-created by build.bat (do not commit)
└── README.md
```

---

## Build the EXE (do this once on your machine)

### 1. Install Python

Download Python 3.9+ from https://www.python.org/downloads/ and **check "Add Python to PATH"** during install.

### 2. Build

```cmd
cd chat2db-connector
build.bat
```

Result: `dist\Chat2DBConnector.exe` (single file, ~240 MB, runs on any Win10/11 without Python).

> If you use **miniconda** as your Python: that's fine for building, but the EXE itself has no Python dependency.

---

## Distribute to colleagues

For each user:

1. On **their** machine, generate an SSH key:
   ```powershell
   ssh-keygen -t ed25519 -f $env:USERPROFILE\.ssh\id_ed25519
   ```
   Just press Enter at all prompts (no passphrase).

2. **They** send you the contents of `id_ed25519.pub` (the one with `.pub`).

3. On the Linux server (as `vscode`):
   ```bash
   mkdir -p ~/.ssh
   chmod 700 ~/.ssh
   echo "<paste public key here>" >> ~/.ssh/authorized_keys
   chmod 600 ~/.ssh/authorized_keys
   ```

4. They put `Chat2DBConnector.exe` anywhere (Desktop is fine), double-click to run, fill in:
   - Host: `192.168.0.197`
   - User: `vscode`
   - Private key: `C:\Users\<them>\.ssh\id_ed25519`
   - Local/remote ports: 10825 / 10825
   - Hit **Connect**

Config is auto-saved to `C:\Users\<them>\.chat2db-connector\config.json`.

---

## Why PySide6 + a venv? (the long story)

Two DLL-loading bugs forced the current shape:

1. **tkinter** — first build used the built-in `tkinter`. On a miniconda
   Python, `tcl86t.dll` / `tk86t.dll` live in `miniconda3\Library\bin\`,
   not the standard place PyInstaller's hook looks. EXE crashed with
   `DLL load failed while importing _tkinter`.
   **Fix: switch GUI to PySide6** — its Qt DLLs are bundled inside the
   PyPI wheel, so PyInstaller packs them correctly.

2. **cryptography (paramiko dependency)** — the miniconda-installed
   `cryptography` is a conda build that links against
   `libcrypto-3-x64.dll` / `libssl-3-x64.dll` from
   `miniconda3\Library\bin\`. PyInstaller still couldn't find them, so
   the EXE crashed with `DLL load failed while importing _rust`.
   **Fix: build inside a venv.** A `pip install cryptography` in a
   fresh venv pulls the PyPI wheel, which **statically links** OpenSSL
   into `_rust.pyd` — zero external DLLs to chase.

So `build.bat` creates a local `.venv` and runs PyInstaller from there.
Don't run PyInstaller from your global / conda Python — you'll get the
same DLL mess again.

---

## Make it smaller (optional)

The Qt DLLs dominate the size. Options:

| Option | Size | Trade-off |
| --- | --- | --- |
| `nuitka` instead of `pyinstaller` | ~80 MB | More complex setup, longer first build |
| Build with `--exclude-module` to drop unused Qt modules (QtMultimedia, QtWebEngine, ...) | ~150 MB | Need to test each excluded module |
| Use UPX compression on the EXE | ~120 MB | Slower startup, sometimes flagged by antivirus |

Not worth doing unless you really need to ship it on flaky networks.

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `Auth failed` | Private key doesn't match server's `authorized_keys`. Check the user, the file path, and that the key has no passphrase. |
| `Local port 10825 already in use` | Previous run left the tunnel up, or some other app is using it. Close & retry, or change the local port. |
| `Connection refused` / timeout | Server firewall blocks port 22, or `vscode` user's SSH config disallows key auth. |
| Browser opens but shows 404 | Chat2DB has a non-root path. Fill the "URL path" field, e.g. `/chat2db`. |
| Antivirus flags the EXE | PyInstaller EXEs are commonly false-positive. Add an exception or sign the binary. |

---

## Run from source (skip building)

```powershell
cd chat2db-connector
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe chat2db-connector.py
```

(Or just run `build.bat` and use the EXE it produces.)
