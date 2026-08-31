import datetime
import threading
import time

import uvicorn
import webview

from app.db import SessionLocal, get_db_path
from app.main import app
from app.services.backup import backup_database, get_backup_dir

PORT = 8731


def _run_server(server: uvicorn.Server) -> None:
    server.run()


def main() -> None:
    config = uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=_run_server, args=(server,), daemon=True)
    thread.start()

    while not server.started:
        time.sleep(0.05)

    webview.create_window(
        "Comptes", f"http://127.0.0.1:{PORT}", width=1280, height=850, fullscreen=True
    )
    webview.start()

    server.should_exit = True
    thread.join(timeout=5)

    db = SessionLocal()
    try:
        backup_dir = get_backup_dir(db)
    finally:
        db.close()

    timestamp = datetime.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    backup_database(get_db_path(), backup_dir, timestamp)


if __name__ == "__main__":
    main()
