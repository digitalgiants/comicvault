from __future__ import annotations

import logging
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

LOGIN_URL = "/accounts/login/"
DOWNLOAD_URL = "/download/"
DOWNLOAD_TIMEOUT_MS = 20 * 60 * 1000


class FetchError(RuntimeError):
    """Raised when the GCD login or download flow doesn't behave as expected."""


def fetch_dump(base_url: str, username: str, password: str, dump_dir: Path) -> Path:
    """Logs into comics.org and downloads the current SQLite dump.

    Fails loudly (FetchError) rather than retrying silently if the site's
    login form or download page has changed shape.
    """
    dump_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        # --no-sandbox is required for Chromium running as root in a container
        browser = p.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page(accept_downloads=True)
        try:
            _login(page, base_url, username, password)
            dump_path = _download_sqlite_dump(page, base_url, dump_dir)
        finally:
            browser.close()

    return dump_path


def _login(page, base_url: str, username: str, password: str) -> None:
    # "networkidle" is unreliable on real-world sites -- comics.org apparently
    # never goes fully network-idle within the navigation timeout (background
    # polling/analytics), so goto() itself would time out even though the page
    # loaded fine. "load" plus the locators' own auto-waiting is what's
    # actually needed before interacting with the form.
    page.goto(f"{base_url}{LOGIN_URL}", wait_until="load", timeout=60_000)

    try:
        page.get_by_label(re.compile("username", re.I)).fill(username)
        page.get_by_label(re.compile("password", re.I)).fill(password)
    except PlaywrightTimeoutError as exc:
        raise FetchError(
            "Could not find username/password fields on the GCD login page "
            "-- the page markup may have changed."
        ) from exc

    page.get_by_role("button", name=re.compile("log ?in", re.I)).click()
    page.wait_for_load_state("load", timeout=60_000)

    if page.locator("form#login-form, input[name=password]").count() > 0:
        raise FetchError("GCD login did not succeed -- still on a login form after submitting.")


def _download_sqlite_dump(page, base_url: str, dump_dir: Path) -> Path:
    page.goto(f"{base_url}{DOWNLOAD_URL}", wait_until="load", timeout=60_000)

    checkbox = page.get_by_role(
        "checkbox", name=re.compile("read and accept the GCD data licensing terms", re.I)
    )
    try:
        checkbox.check(timeout=10_000)
    except PlaywrightTimeoutError as exc:
        raise FetchError(
            "Could not find the license-acceptance checkbox on the GCD download page "
            "-- the page markup may have changed."
        ) from exc

    download_button = page.get_by_role("button", name=re.compile("download sqlite dump", re.I))
    if download_button.count() == 0:
        raise FetchError(
            "Could not find the 'Download SQLite Dump' button -- GCD may have "
            "renamed or removed the SQLite export option."
        )

    try:
        with page.expect_download(timeout=DOWNLOAD_TIMEOUT_MS) as download_info:
            download_button.click()
        download = download_info.value
    except PlaywrightTimeoutError as exc:
        raise FetchError("GCD SQLite dump download did not start within the timeout.") from exc

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    zip_path = dump_dir / f"gcd-{timestamp}.zip"
    download.save_as(zip_path)
    logger.info("Saved GCD dump archive to %s", zip_path)

    return _extract_sqlite_db(zip_path, dump_dir, timestamp)


def _extract_sqlite_db(zip_path: Path, dump_dir: Path, timestamp: str) -> Path:
    """GCD serves the SQLite dump as a zip containing a single dated .db file."""
    with zipfile.ZipFile(zip_path) as zf:
        members = zf.namelist()
        if len(members) != 1:
            raise FetchError(
                f"Expected exactly one file in the GCD dump archive, found {len(members)}: {members}"
            )
        dest = dump_dir / f"gcd-{timestamp}.db"
        with zf.open(members[0]) as src, dest.open("wb") as out:
            while chunk := src.read(1024 * 1024):
                out.write(chunk)

    zip_path.unlink()
    logger.info("Extracted GCD dump to %s", dest)
    return dest
