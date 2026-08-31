import datetime
import threading
import time
from pathlib import Path

import uvicorn
import webview

from app.db import get_db_path
from app.main import app
from app.services.backup import backup_database

PORT = 8731
BACKUP_DIR_ENV_DEFAULT = Path.home() / "Google Drive" / "ComptesAppBackups"


def _run_server(server: uvicorn.Server) -> None:
    server.run()


def main() -> None:
    config = uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=_run_server, args=(server,), daemon=True)
    thread.start()

    while not server.started:
        time.sleep(0.05)

    webview.create_window("Comptes", f"http://127.0.0.1:{PORT}", width=1280, height=850)
    webview.start()

    server.should_exit = True
    thread.join(timeout=5)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    backup_database(get_db_path(), BACKUP_DIR_ENV_DEFAULT, timestamp)


if __name__ == "__main__":
    main()
