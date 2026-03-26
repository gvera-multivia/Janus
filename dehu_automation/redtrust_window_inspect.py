import os
import subprocess
import sys
import time
from typing import List, Tuple

import pyautogui
from pywinauto import Desktop
from pywinauto.keyboard import send_keys

from utils.logger import get_logger

logger = get_logger()
desktop = Desktop(backend="uia")

WAIT_TIME = {
    "SHORT": 0.5,
    "MEDIUM": 1.0,
    "LONG": 2.0,
    "X_LONG": 3.0,
}

REDTRUST_EXECUTABLE_PATHS = [
    r"C:\Program Files\RedTrust\RTTrayApp.exe",
    r"C:\Program Files\RedTrust\RTLaunchTray.exe",
    r"C:\Program Files\RedTrust\RedTrustAgent.exe",
    r"C:\Program Files (x86)\RedTrust\RTTrayApp.exe",
    r"C:\Program Files (x86)\RedTrust\RTLaunchTray.exe",
    r"C:\Program Files (x86)\RedTrust\RedTrustAgent.exe",
    r"C:\ProgramData\RedTrust\RedTrustAgent.exe",
]

REDTRUST_ENV_VARS = [
    "REDTRUST_EXE",
    "REDTRUST_PATH",
]

HIDDEN_ICONS_TITLES = [
    "Botón de contenido adicional de notificaciones",
    "Show hidden icons",
    "Mostrar iconos ocultos",
]

TRAY_WINDOW_KEYWORDS = [
    "desbordamiento de notificaciones",
    "notification overflow",
    "overflow",
    "barra de tareas",
    "taskbar",
]

EXCLUDED_WINDOW_KEYWORDS = [
    "visual studio code",
    "google chrome",
    "microsoft edge",
    "chatgpt",
]

EXCLUDED_PROCESS_NAMES = {
    "code.exe",
    "chrome.exe",
    "msedge.exe",
}

REDTRUST_AGENT_TITLE = "RedTrust Agent"
REDTRUST_AGENT_PROCESS = "rttrayapp.exe"


def get_process_name(pid: int) -> str:
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


def get_window_metadata(window) -> Tuple[str, str, str, int, str]:
    try:
        title = window.window_text() or ""
    except Exception:
        title = ""

    try:
        class_name = window.element_info.class_name or ""
    except Exception:
        class_name = ""

    try:
        control_type = window.element_info.control_type or ""
    except Exception:
        control_type = ""

    try:
        process_id = window.element_info.process_id or 0
    except Exception:
        process_id = 0

    process_name = get_process_name(process_id)
    return title, class_name, control_type, process_id, process_name


def log_window(prefix, window):
    title, class_name, control_type, process_id, process_name = get_window_metadata(window)
    logger.info(
        "%s title='%s' class='%s' type='%s' pid=%s process='%s'",
        prefix,
        title,
        class_name,
        control_type,
        process_id,
        process_name,
    )


def get_redtrust_executable_candidates():
    candidates = []

    for env_var in REDTRUST_ENV_VARS:
        env_value = os.environ.get(env_var)
        if env_value:
            logger.info("RedTrust: environment override %s=%s", env_var, env_value)
            candidates.append(env_value)

    local_app_data = os.environ.get("LOCALAPPDATA", "")
    app_data = os.environ.get("APPDATA", "")
    candidates.extend(
        [
            os.path.join(local_app_data, "Programs", "RedTrust", "RTTrayApp.exe"),
            os.path.join(local_app_data, "Programs", "RedTrust", "RTLaunchTray.exe"),
            os.path.join(local_app_data, "RedTrust", "RTTrayApp.exe"),
            os.path.join(local_app_data, "RedTrust", "RTLaunchTray.exe"),
            os.path.join(app_data, "RedTrust", "RTTrayApp.exe"),
            os.path.join(app_data, "RedTrust", "RTLaunchTray.exe"),
        ]
    )
    candidates.extend(REDTRUST_EXECUTABLE_PATHS)

    unique_candidates = []
    seen = set()
    for candidate in candidates:
        normalized = os.path.normpath(candidate)
        if normalized in seen:
            continue
        seen.add(normalized)
        unique_candidates.append(normalized)

    return unique_candidates


def get_taskbar():
    for title in ["Barra de tareas", "Taskbar"]:
        try:
            taskbar = desktop.window(title_re=f".*{title}.*", control_type="Pane")
            if taskbar.exists(timeout=2):
                log_window("RedTrust: taskbar detected", taskbar)
                return taskbar
        except Exception:
            continue

    logger.warning("RedTrust: taskbar pane not found")
    return None


def open_hidden_icons(taskbar):
    if taskbar is None:
        return False

    logger.info("RedTrust: trying to open hidden notification icons")
    for title in HIDDEN_ICONS_TITLES:
        try:
            more_button = taskbar.child_window(title=title, control_type="Button")
            if more_button.exists(timeout=2):
                more_button.click_input()
                time.sleep(1)
                logger.info("RedTrust: hidden notification area opened using '%s'", title)
                return True
        except Exception:
            continue

    logger.info("RedTrust: hidden notification button not found")
    return False


def is_tray_window(window) -> bool:
    title, class_name, _, _, process_name = get_window_metadata(window)
    lowered = f"{title} {class_name}".lower()

    if process_name in EXCLUDED_PROCESS_NAMES:
        return False

    return any(keyword in lowered for keyword in TRAY_WINDOW_KEYWORDS)


def find_redtrust_icon(timeout_seconds=15):
    logger.info("RedTrust: scanning tray/overflow windows for icon up to %s seconds", timeout_seconds)
    start_time = time.time()

    while time.time() - start_time < timeout_seconds:
        for window in desktop.windows():
            if not is_tray_window(window):
                continue

            log_window("RedTrust: tray candidate", window)
            try:
                for button in window.descendants(control_type="Button"):
                    name = (button.window_text() or "").lower()
                    element_name = (button.element_info.name or "").lower()
                    if "redtrust" in name or "redtrust" in element_name:
                        logger.info(
                            "RedTrust: icon found in tray window '%s' with text '%s' / '%s'",
                            window.window_text(),
                            name,
                            element_name,
                        )
                        return button, window
            except Exception:
                continue

        time.sleep(1)

    logger.warning("RedTrust: tray scan did not find icon")
    return None, None


def launch_redtrust_if_needed():
    logger.info("RedTrust: icon not found, trying direct launch")

    for candidate in get_redtrust_executable_candidates():
        logger.info("RedTrust: checking executable candidate %s", candidate)
        if not os.path.exists(candidate):
            continue

        try:
            subprocess.Popen([candidate], shell=False)
            logger.info("RedTrust: launched from %s", candidate)
            time.sleep(6)
            return True
        except Exception as exc:
            logger.warning("RedTrust: unable to launch from %s: %s", candidate, exc)

    logger.error("RedTrust: no executable found in configured candidate paths")
    return False


def capture_window_snapshot():
    snapshot = set()
    for window in desktop.windows():
        title, class_name, _, process_id, process_name = get_window_metadata(window)
        snapshot.add((title, class_name, process_id, process_name))
    return snapshot


def click_certificates_menu():
    logger.info("RedTrust: searching context menu entry related to certificates")
    for window in desktop.windows():
        if is_tray_window(window):
            continue

        title, class_name, control_type, process_id, process_name = get_window_metadata(window)
        try:
            for element in window.descendants():
                text = f"{element.window_text() or ''} {element.element_info.name or ''}".lower()
                if "certificado" not in text:
                    continue

                logger.info(
                    "RedTrust: clicking certificate menu item in window title='%s' class='%s' type='%s' pid=%s process='%s'",
                    title,
                    class_name,
                    control_type,
                    process_id,
                    process_name,
                )
                element.click_input()
                return True
        except Exception:
            continue

    logger.warning("RedTrust: certificate-related menu item not found")
    return False


def open_certificates_from_tray(redtrust_button):
    logger.info("RedTrust: right-clicking tray icon as primary strategy")
    try:
        redtrust_button.click_input(button="right")
        time.sleep(1)
        if click_certificates_menu():
            logger.info("RedTrust: certificate menu opened after right click")
            return True
    except Exception as exc:
        logger.warning("RedTrust: right click flow failed: %s", exc)

    logger.info("RedTrust: falling back to left click on tray icon")
    try:
        redtrust_button.click_input()
        time.sleep(1)
        if click_certificates_menu():
            logger.info("RedTrust: certificate menu opened after left click")
            return True
    except Exception as exc:
        logger.warning("RedTrust: left click flow failed: %s", exc)

    logger.error("RedTrust: unable to open certificate menu from tray icon")
    return False


def is_excluded_window(title: str, class_name: str, process_name: str) -> bool:
    lowered_title = title.lower()
    lowered_class = class_name.lower()

    if any(keyword in lowered_title for keyword in EXCLUDED_WINDOW_KEYWORDS):
        return True

    if process_name in EXCLUDED_PROCESS_NAMES:
        return True

    if lowered_class == "chrome_widgetwin_1":
        return True

    return False


def wait_for_redtrust_agent_window(timeout_seconds=30):
    logger.info(
        "RedTrust: waiting for real agent window title='%s' process='%s' up to %s seconds",
        REDTRUST_AGENT_TITLE,
        REDTRUST_AGENT_PROCESS,
        timeout_seconds,
    )
    start_time = time.time()

    while time.time() - start_time < timeout_seconds:
        for window in desktop.windows():
            title, class_name, control_type, process_id, process_name = get_window_metadata(window)
            excluded = is_excluded_window(title, class_name, process_name)
            title_match = title.strip().lower() == REDTRUST_AGENT_TITLE.lower()
            process_match = process_name == REDTRUST_AGENT_PROCESS
            logger.info(
                "RedTrust: agent candidate title='%s' class='%s' type='%s' pid=%s process='%s' excluded=%s title_match=%s process_match=%s",
                title,
                class_name,
                control_type,
                process_id,
                process_name,
                excluded,
                title_match,
                process_match,
            )

            if excluded or not title_match or not process_match:
                continue

            try:
                window.set_focus()
            except Exception:
                pass

            logger.info("RedTrust: real agent window detected and focused")
            return window

        time.sleep(1)

    logger.error("RedTrust: real agent window was not detected within timeout")
    return None


def get_agent_control_snapshot(agent_window):
    snapshot = {}
    for control_type in ["Edit", "Button", "List", "Pane", "DataItem", "CheckBox", "Text"]:
        try:
            snapshot[control_type] = len(agent_window.descendants(control_type=control_type))
        except Exception:
            snapshot[control_type] = -1
    return snapshot


def wait_for_agent_controls(agent_window, timeout_seconds=8):
    logger.info("RedTrust: waiting for RedTrust Agent controls to be ready up to %s seconds", timeout_seconds)
    start_time = time.time()
    last_logged_slot = None

    while time.time() - start_time < timeout_seconds:
        snapshot = get_agent_control_snapshot(agent_window)
        current_slot = int(time.time() - start_time) // 2
        if current_slot != last_logged_slot:
            logger.info(
                "RedTrust: agent control snapshot Edit=%s Button=%s List=%s Pane=%s DataItem=%s CheckBox=%s Text=%s",
                snapshot["Edit"],
                snapshot["Button"],
                snapshot["List"],
                snapshot["Pane"],
                snapshot["DataItem"],
                snapshot["CheckBox"],
                snapshot["Text"],
            )
            last_logged_slot = current_slot

        if snapshot["Edit"] > 0:
            logger.info("RedTrust: agent window is ready because at least one Edit control is available")
            return True

        time.sleep(1)

    logger.error("RedTrust: agent controls were not ready within timeout")
    return False


def log_agent_child_structure(agent_window):
    logger.info("RedTrust: dumping immediate child structure of RedTrust Agent")
    try:
        children = agent_window.children()
        logger.info("RedTrust: RedTrust Agent has %s immediate children", len(children))
        for index, child in enumerate(children):
            try:
                child_title, child_class, child_type, child_pid, child_process = get_window_metadata(child)
                logger.info(
                    "RedTrust: child index=%s title='%s' class='%s' type='%s' pid=%s process='%s'",
                    index,
                    child_title,
                    child_class,
                    child_type,
                    child_pid,
                    child_process,
                )
            except Exception as exc:
                logger.info("RedTrust: unable to describe child index=%s: %s", index, exc)
    except Exception as exc:
        logger.warning("RedTrust: unable to dump RedTrust Agent children: %s", exc)


def click_agent_relative(agent_window, x_ratio, y_ratio, description):
    try:
        rect = agent_window.rectangle()
        x = rect.left + int((rect.right - rect.left) * x_ratio)
        y = rect.top + int((rect.bottom - rect.top) * y_ratio)
        pyautogui.click(x=x, y=y)
        logger.info("RedTrust: clicked %s at relative position (%.2f, %.2f) => (%s, %s)", description, x_ratio, y_ratio, x, y)
        return True
    except Exception as exc:
        logger.error("RedTrust: failed bounded click for %s: %s", description, exc)
        return False


def get_redtrust_process_windows():
    windows = []
    for window in desktop.windows():
        title, class_name, control_type, process_id, process_name = get_window_metadata(window)
        if process_name != REDTRUST_AGENT_PROCESS:
            continue
        windows.append(window)
        logger.info(
            "RedTrust: process window candidate title='%s' class='%s' type='%s' pid=%s process='%s'",
            title,
            class_name,
            control_type,
            process_id,
            process_name,
        )
    return windows


def wait_for_redtrust_content_window(timeout_seconds=30):
    logger.info("RedTrust: waiting for any content window from process '%s' up to %s seconds", REDTRUST_AGENT_PROCESS, timeout_seconds)
    start_time = time.time()

    while time.time() - start_time < timeout_seconds:
        windows = get_redtrust_process_windows()
        if windows:
            return windows
        time.sleep(1)

    logger.warning("RedTrust: no process windows found beyond the main agent window")
    return []


def find_filter_edit_across_redtrust_windows(timeout_seconds=30):
    logger.info("RedTrust: waiting for a usable Edit control across RedTrust process windows up to %s seconds", timeout_seconds)
    start_time = time.time()
    last_logged_slot = None

    while time.time() - start_time < timeout_seconds:
        windows = get_redtrust_process_windows()
        for window in windows:
            title, class_name, control_type, process_id, process_name = get_window_metadata(window)
            try:
                edits = window.descendants(control_type="Edit")
            except Exception:
                edits = []

            current_slot = int(time.time() - start_time) // 2
            if current_slot != last_logged_slot:
                logger.info(
                    "RedTrust: window title='%s' class='%s' type='%s' pid=%s has %s Edit controls",
                    title,
                    class_name,
                    control_type,
                    process_id,
                    len(edits),
                )
                last_logged_slot = current_slot

            for index, edit in enumerate(edits):
                try:
                    rect = edit.rectangle()
                    visible = rect.width() > 0 and rect.height() > 0
                except Exception:
                    visible = False

                try:
                    enabled = edit.is_enabled()
                except Exception:
                    enabled = True

                logger.info(
                    "RedTrust: cross-window edit candidate window='%s' index=%s visible=%s enabled=%s",
                    title,
                    index,
                    visible,
                    enabled,
                )

                if visible and enabled:
                    logger.info("RedTrust: using Edit index=%s from window '%s' as filter", index, title)
                    return window, edit

            if edits:
                logger.info("RedTrust: falling back to first Edit in window '%s'", title)
                return window, edits[0]

        time.sleep(1)

    logger.warning("RedTrust: no usable Edit control found across RedTrust process windows")
    return None, None


def wait_for_redtrust_window_diagnostics(baseline_snapshot, timeout_seconds=30):
    logger.info("RedTrust: waiting up to %s seconds for new candidate windows after clicking 'Certificados'", timeout_seconds)
    start_time = time.time()
    seen = set()

    while time.time() - start_time < timeout_seconds:
        for window in desktop.windows():
            title, class_name, control_type, process_id, process_name = get_window_metadata(window)
            signature = (title, class_name, process_id, process_name)
            if signature in baseline_snapshot or signature in seen:
                continue

            seen.add(signature)
            excluded = is_excluded_window(title, class_name, process_name)
            logger.info(
                "RedTrust: new window candidate title='%s' class='%s' type='%s' pid=%s process='%s' excluded=%s",
                title,
                class_name,
                control_type,
                process_id,
                process_name,
                excluded,
            )

        time.sleep(1)

    logger.info("RedTrust: diagnostic wait finished")
    return True


def search_certificate(agent_window, filter_value: str):
    content_windows = wait_for_redtrust_content_window(timeout_seconds=5)
    if not content_windows:
        logger.warning("RedTrust: no additional content windows found, continuing with main agent window")

    target_window, filter_edit = find_filter_edit_across_redtrust_windows(timeout_seconds=35)
    if target_window is None:
        target_window = agent_window

    if not reset_redtrust_preselection(target_window):
        logger.error("RedTrust: unable to normalize previous RedTrust preselection state")
        return False

    try:
        target_window.set_focus()
    except Exception:
        pass

    if filter_edit is not None:
        try:
            filter_edit.click_input()
            time.sleep(0.5)
            try:
                filter_edit.set_edit_text("")
                logger.info("RedTrust: filter edit cleared with set_edit_text")
            except Exception:
                send_keys("^a{BACKSPACE}")
                logger.info("RedTrust: filter edit cleared with keyboard fallback")

            target_title, _, _, _, _ = get_window_metadata(target_window)
            logger.info("RedTrust: typing client id '%s' into selected filter edit inside window '%s'", filter_value, target_title)
            filter_edit.type_keys(filter_value, with_spaces=True)
            time.sleep(0.5)
            send_keys("{ENTER}")
            logger.info("RedTrust: search launched with Enter")
            return True
        except Exception as exc:
            logger.error("RedTrust: failed while typing search value inside agent window: %s", exc)

    logger.warning("RedTrust: no UIA edit available, using bounded fallback focused inside RedTrust window")
    if not click_agent_relative(target_window, 0.50, 0.18, "search area fallback"):
        return False

    time.sleep(0.5)
    send_keys("^a{BACKSPACE}")
    logger.info("RedTrust: cleared fallback search area with keyboard")
    send_keys(filter_value)
    logger.info("RedTrust: typed client id '%s' with bounded fallback", filter_value)
    time.sleep(0.5)
    send_keys("{ENTER}")
    logger.info("RedTrust: search launched with Enter using bounded fallback")
    return True


def reset_redtrust_preselection(agent_window):
    logger.info("RedTrust: normalizing previous preselection state before filtering")

    try:
        for element in agent_window.descendants():
            text = f"{element.window_text() or ''} {element.element_info.name or ''}".lower().strip()
            auto_id = ""
            try:
                auto_id = (element.element_info.automation_id or "").lower()
            except Exception:
                pass

            if "seleccionar todos" in text or "deseleccionar todos" in text or auto_id == "selectalltoggle":
                logger.info("RedTrust: toggling 'Seleccionar todos / Deseleccionar todos' control")
                element.click_input()
                time.sleep(0.2)
                element.click_input()
                break
        else:
            logger.warning("RedTrust: select-all checkbox not exposed by UIA, using bounded fallback")
            if not click_agent_relative(agent_window, 0.04, 0.34, "select all checkbox fallback"):
                return False
            time.sleep(0.2)
            if not click_agent_relative(agent_window, 0.04, 0.34, "select all checkbox fallback"):
                return False
    except Exception as exc:
        logger.warning("RedTrust: failed to normalize select-all state by UIA: %s", exc)
        if not click_agent_relative(agent_window, 0.04, 0.34, "select all checkbox fallback"):
            return False
        time.sleep(0.2)
        if not click_agent_relative(agent_window, 0.04, 0.34, "select all checkbox fallback"):
            return False

    try:
        for element in agent_window.descendants():
            text = f"{element.window_text() or ''} {element.element_info.name or ''}".lower().strip()
            auto_id = ""
            try:
                auto_id = (element.element_info.automation_id or "").lower()
            except Exception:
                pass

            if text == "todos" or auto_id == "radioall":
                logger.info("RedTrust: selecting 'Todos' filter mode")
                element.click_input()
                return True
    except Exception as exc:
        logger.warning("RedTrust: could not click 'Todos' by UIA: %s", exc)

    logger.info("RedTrust: using bounded fallback for 'Todos' radio")
    return click_agent_relative(agent_window, 0.40, 0.16, "todos radio fallback")


def get_result_candidates(agent_window):
    candidates = []
    control_types = ["DataItem", "ListItem", "CheckBox", "Text"]

    for control_type in control_types:
        try:
            for element in agent_window.descendants(control_type=control_type):
                text = f"{element.window_text() or ''} {element.element_info.name or ''}".strip()
                if not text:
                    continue
                candidates.append((control_type, element, text))
        except Exception:
            continue

    return candidates


def select_certificate_result(agent_window, filter_value: str):
    logger.info("RedTrust: waiting for filtered result matching '%s'", filter_value)
    time.sleep(1)
    start_time = time.time()

    while time.time() - start_time < 12:
        all_candidates = []
        for window in get_redtrust_process_windows():
            title, _, _, _, _ = get_window_metadata(window)
            candidates = get_result_candidates(window)
            logger.info("RedTrust: found %s candidate result controls inside RedTrust window '%s'", len(candidates), title)
            all_candidates.extend((window, control_type, element, text) for control_type, element, text in candidates)

        for window, control_type, element, text in all_candidates:
            lowered = text.lower()
            if filter_value.lower() not in lowered:
                continue

            window_title, _, _, _, _ = get_window_metadata(window)
            logger.info(
                "RedTrust: selecting result control type='%s' text='%s' in window '%s'",
                control_type,
                text,
                window_title,
            )
            try:
                element.click_input()
                time.sleep(0.3)
                return True
            except Exception as exc:
                logger.warning("RedTrust: unable to click result '%s': %s", text, exc)

        time.sleep(0.5)

    logger.warning("RedTrust: no explicit result matched '%s', using bounded window fallback inspired by working script", filter_value)
    return click_agent_relative(agent_window, 0.50, 0.45, "result area fallback")


def click_accept(agent_window):
    logger.info("RedTrust: searching accept button inside RedTrust Agent")
    for window in get_redtrust_process_windows():
        title, _, _, _, _ = get_window_metadata(window)
        try:
            for element in window.descendants():
                text = f"{element.window_text() or ''} {element.element_info.name or ''}".lower().strip()
                if "aceptar" not in text:
                    continue

                logger.info("RedTrust: clicking accept-like control with text '%s' in window '%s'", text, title)
                try:
                    element.click_input()
                except Exception:
                    rect = element.rectangle()
                    pyautogui.click(x=rect.left + ((rect.right - rect.left) // 2), y=rect.top + ((rect.bottom - rect.top) // 2))
                return True
        except Exception as exc:
            logger.warning("RedTrust: unable to inspect accept controls in window '%s': %s", title, exc)

    logger.warning("RedTrust: no accept control exposed by UIA, using bounded fallback in lower-right area")
    return click_agent_relative(agent_window, 0.68, 0.93, "accept button fallback")


def diagnose_redtrust_open() -> bool:
    logger.info("Starting RedTrust open diagnostic")

    taskbar = get_taskbar()
    open_hidden_icons(taskbar)

    redtrust_button, owner_window = find_redtrust_icon(timeout_seconds=15)
    if redtrust_button is None:
        if not launch_redtrust_if_needed():
            return False
        taskbar = get_taskbar()
        open_hidden_icons(taskbar)
        redtrust_button, owner_window = find_redtrust_icon(timeout_seconds=20)

    if redtrust_button is None:
        logger.error("RedTrust: tray icon not found after launch attempt")
        return False

    if owner_window is not None:
        log_window("RedTrust: icon owner window", owner_window)
        logger.info("RedTrust: icon owner is_tray_window=%s", is_tray_window(owner_window))

    baseline_snapshot = capture_window_snapshot()
    if not open_certificates_from_tray(redtrust_button):
        return False

    return wait_for_redtrust_window_diagnostics(baseline_snapshot, timeout_seconds=30)


def automate_redtrust(certificates: List[str]) -> bool:
    logger.info("Starting RedTrust full automation for filters: %s", certificates)
    if not certificates:
        logger.error("RedTrust: no filter values received")
        return False

    taskbar = get_taskbar()
    open_hidden_icons(taskbar)

    redtrust_button, owner_window = find_redtrust_icon(timeout_seconds=15)
    if redtrust_button is None:
        if not launch_redtrust_if_needed():
            return False
        taskbar = get_taskbar()
        open_hidden_icons(taskbar)
        redtrust_button, owner_window = find_redtrust_icon(timeout_seconds=20)

    if redtrust_button is None:
        logger.error("RedTrust: tray icon not found after launch attempt")
        return False

    if owner_window is not None:
        log_window("RedTrust: icon owner window", owner_window)

    if not open_certificates_from_tray(redtrust_button):
        return False

    agent_window = wait_for_redtrust_agent_window(timeout_seconds=30)
    if agent_window is None:
        return False

    if not wait_for_agent_controls(agent_window, timeout_seconds=8):
        log_agent_child_structure(agent_window)
        logger.warning("RedTrust: proceeding with bounded fallbacks because UIA controls did not appear")

    filter_value = certificates[0]
    if not search_certificate(agent_window, filter_value):
        logger.error("RedTrust: unable to search certificate '%s'", filter_value)
        return False

    if not select_certificate_result(agent_window, filter_value):
        logger.error("RedTrust: unable to select filtered certificate '%s'", filter_value)
        return False

    if not click_accept(agent_window):
        logger.error("RedTrust: unable to confirm preselection for '%s'", filter_value)
        return False

    logger.info("RedTrust: full pre-selection flow completed for '%s'", filter_value)
    return True


def run_redtrust_flow(selection_value: str) -> bool:
    logger.info("Starting RedTrust full flow for '%s'", selection_value)
    if not selection_value or not selection_value.strip():
        logger.error("Empty selection value received for RedTrust flow")
        return False

    return automate_redtrust([selection_value])


if __name__ == "__main__":
    if len(sys.argv) > 1:
        action = sys.argv[1]

        if action == "search":
            cert_id = "27388"
            if len(sys.argv) > 2 and sys.argv[2].strip() != "":
                cert_id = sys.argv[2]
            logger.info("CLI search mode for RedTrust filter '%s'", cert_id)
            result = automate_redtrust([cert_id])
            sys.exit(0 if result else 1)

        if action == "diagnose":
            logger.info("CLI diagnose mode for RedTrust")
            result = diagnose_redtrust_open()
            sys.exit(0 if result else 1)

        if action == "full":
            selection_value = "27388"
            if len(sys.argv) > 2 and sys.argv[2].strip() != "":
                selection_value = sys.argv[2]
            logger.info("CLI full mode for selection value '%s'", selection_value)
            result = run_redtrust_flow(selection_value)
            sys.exit(0 if result else 1)

        logger.error("Unknown action. Use 'search', 'diagnose' or 'full'")
        sys.exit(1)

    logger.info("Usage: python redtrust_window_inspect.py search|diagnose|full [value]")
    logger.info("Running default full flow")
    result = run_redtrust_flow("27388")
    sys.exit(0 if result else 1)
