"""Optional real-browser smoke test. pip install playwright && playwright install chromium.

Runs an isolated server and copies generated silence fixtures, never real music.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent.parent


def main():
    with tempfile.TemporaryDirectory(prefix="musictag-browser-") as temporary:
        root = Path(temporary)
        music = root / "music"
        music.mkdir()
        for extension in ["mp3", "flac", "wav"]:
            shutil.copy2(BASE / "library" / "tests" / "fixtures" / f"silence.{extension}", music)
        env = {
            **os.environ,
            "MUSICTAG_STATE": str(root / "state"),
            "MUSICTAG_WORKER": "true",
            "ALLOWED_HOSTS": "127.0.0.1,localhost",
        }
        for command in [["migrate", "--noinput"], ["collectstatic", "--noinput"]]:
            subprocess.run(
                [sys.executable, "manage.py", *command],
                cwd=BASE,
                env=env,
                check=True,
                stdout=subprocess.DEVNULL,
            )
        log = (root / "server.log").open("w+")
        server = subprocess.Popen(
            [sys.executable, "manage.py", "runserver", "127.0.0.1:8765", "--noreload"],
            cwd=BASE,
            env=env,
            stdout=log,
            stderr=log,
        )
        try:
            for _ in range(100):
                try:
                    urllib.request.urlopen("http://127.0.0.1:8765/api/health", timeout=1).close()
                    break
                except (OSError, urllib.error.URLError):
                    time.sleep(0.1)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": 1440, "height": 1000})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("dialog", lambda dialog: dialog.accept())
                page.goto("http://127.0.0.1:8765/")
                page.locator("#root").fill(str(music))
                page.get_by_role("button", name="Choose folder & scan").click()
                page.get_by_role("heading", name="Scan · completed").wait_for(timeout=30000)
                page.get_by_role("link", name="Return to library").click()
                page.locator("#lock-form button").click()
                page.get_by_role("link", name="Tracks", exact=False).first.click()
                page.locator("tr[data-track]").first.wait_for()
                page.locator("tr[data-track] .track-title a").first.click()
                page.locator("#inspector .tag-editor").wait_for()
                page.locator("#inspector [name=field_TITLE]").fill("Browser edited")
                page.locator("#inspector button.save").click()
                page.locator("#inspector .dirty-status").filter(has_text="Up to date").wait_for()
                page.locator("#select-page").check()
                page.locator("#edit-selection").click()
                page.get_by_role("heading", name="Edit selection").wait_for()
                page.locator(".bulk-editor [name=field_ALBUM]").fill("Browser album")
                page.get_by_role("button", name="Preview changes").click()
                page.get_by_role("heading", name="Review your changes").wait_for()
                page.get_by_role("button", name="Apply changes", exact=True).click()
                page.get_by_role("heading", name="Bulk · completed").wait_for(timeout=30000)
                page.get_by_role("link", name="Operation history", exact=True).click()
                page.locator(".history-card").first.get_by_role("button", name="Undo", exact=False).click()
                page.get_by_role("heading", name="Undo · completed").wait_for(timeout=30000)
                page.goto("http://127.0.0.1:8765/tracks")
                page.locator("[data-play]").first.click()
                page.wait_for_function("document.querySelector('#audio').src.includes('/api/audio/')")
                for width in [1024, 1920]:
                    page.set_viewport_size({"width": width, "height": 1000})
                    assert page.evaluate("document.body.scrollWidth <= window.innerWidth")
                browser.close()
                assert not errors, errors
                print(
                    "Browser smoke passed: onboard, scan, edit, bulk preview/apply, undo, player, responsive shell."
                )
        except Exception:
            log.flush()
            print((root / "server.log").read_text(), file=sys.stderr)
            raise
        finally:
            server.terminate()
            server.wait(timeout=15)
            log.close()


if __name__ == "__main__":
    main()
