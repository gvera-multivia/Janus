import os
import subprocess
import time

import requests
from playwright.sync_api import sync_playwright
from pywinauto import Desktop

from utils.logger import get_logger

logger = get_logger()

EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
DEBUG_PORT = 9222


def wait_for_debug_port(timeout_seconds=30):
    logger.info("Waiting for Edge remote debugging port %s", DEBUG_PORT)
    start_time = time.time()

    while time.time() - start_time < timeout_seconds:
        try:
            requests.get(f"http://localhost:{DEBUG_PORT}/json/version", timeout=1)
            logger.info("Edge remote debugging port is ready")
            return
        except Exception:
            time.sleep(1)

    raise RuntimeError("Edge did not open the remote debugging port")


def get_process_name(pid):
    if not pid:
        return ""

    try:
        output = subprocess.check_output(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return ""

    if not output or output.startswith("INFO:"):
        return ""

    first = output.splitlines()[0].strip().strip('"')
    if not first:
        return ""

    return first.split('","')[0].lower()


def focus_edge_window_by_process(timeout_seconds=10):
    logger.info("Waiting for a visible Edge native window by process")
    start_time = time.time()
    excluded_title_signals = ["visual studio code", "google chrome", "chatgpt"]

    while time.time() - start_time < timeout_seconds:
        try:
            windows = Desktop(backend="uia").windows()
        except Exception as exc:
            logger.warning("Unable to enumerate native windows for Edge foreground: %s", exc)
            return False

        for window in windows:
            try:
                class_name = (window.element_info.class_name or "").strip()
            except Exception:
                class_name = ""

            try:
                title = window.window_text() or ""
            except Exception:
                title = ""

            try:
                process_id = window.element_info.process_id or 0
            except Exception:
                process_id = 0

            process_name = get_process_name(process_id)
            lowered_title = title.lower()

            if class_name != "Chrome_WidgetWin_1":
                continue

            if process_name != "msedge.exe":
                continue

            if any(signal in lowered_title for signal in excluded_title_signals):
                continue

            try:
                visible = window.is_visible()
            except Exception:
                visible = True

            if not visible:
                continue

            logger.info(
                "Edge native window located with title '%s', class '%s', pid=%s, process='%s'",
                title,
                class_name,
                process_id,
                process_name,
            )

            try:
                window.restore()
                logger.info("Edge native window restored")
            except Exception:
                pass

            try:
                window.maximize()
                logger.info("Edge native window maximized")
            except Exception:
                pass

            try:
                window.set_focus()
                logger.info("Edge native window foreground applied")
                return True
            except Exception as exc:
                logger.warning("Unable to focus Edge native window: %s", exc)
                return False

        time.sleep(0.5)

    logger.warning("Could not locate a visible Edge native window")
    return False


def start_browser(cliente):
    logger.info("Closing existing Edge processes before starting automation browser")
    subprocess.call("taskkill /f /im msedge.exe >nul 2>&1", shell=True)
    time.sleep(2)

    user_data_dir = f"C:\\temp\\edge_profile_{cliente.nif}"
    logger.info("Using Edge user data dir: %s", user_data_dir)
    os.makedirs(user_data_dir, exist_ok=True)

    launch_args = [
        EDGE_PATH,
        f"--user-data-dir={user_data_dir}",
        f"--remote-debugging-port={DEBUG_PORT}",
        "--no-first-run",
        "--no-default-browser-check",
        "--start-maximized",
    ]

    logger.info("Launching Edge with remote debugging enabled")
    edge_process = subprocess.Popen(launch_args)
    logger.info("Edge launched with pid %s", edge_process.pid)
    logger.info("Edge launch args: user_data_dir=%s remote_debugging_port=%s start_maximized=%s", user_data_dir, DEBUG_PORT, True)
    time.sleep(2)
    wait_for_debug_port()
    focus_edge_window_by_process()

    logger.info("Connecting Playwright to existing Edge instance")
    playwright = sync_playwright().start()
    browser = playwright.chromium.connect_over_cdp(f"http://localhost:{DEBUG_PORT}")

    context = browser.contexts[0]
    if context.pages:
        page = context.pages[0]
    else:
        page = context.new_page()

    page.bring_to_front()
    time.sleep(1)
    logger.info("Edge connected and page brought to front")

    return playwright, browser, context, page
