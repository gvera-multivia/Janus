import re
import threading
import time

from pywinauto import Desktop
from pywinauto.keyboard import send_keys

from utils.logger import get_logger

logger = get_logger()

EXCLUDED_POPUP_WINDOW_KEYWORDS = [
    "visual studio code",
    "terminal",
    "powershell",
    "windows terminal",
]

def _get_window_metadata(window):
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

    return title, class_name, control_type, process_id

def _is_interesting_window(window):
    title, class_name, control_type, _ = _get_window_metadata(window)
    lowered_title = title.lower()
    lowered = f"{title} {class_name} {control_type}".lower()

    if "visual studio code" in lowered or lowered_title.strip() == "code" or " - code" in lowered_title:
        return False

    if any(keyword in lowered for keyword in EXCLUDED_POPUP_WINDOW_KEYWORDS):
        return False

    popup_signals = [
        "seleccionar un certificado",
        "credenciales",
        "certificate",
        "certificado",
        "cl@ve",
    ]
    return any(keyword in lowered for keyword in popup_signals)


def _has_certificate_popup_evidence(window):
    title, class_name, control_type, _ = _get_window_metadata(window)
    lowered_title = title.lower()
    lowered = f"{title} {class_name} {control_type}".lower()

    if "visual studio code" in lowered or lowered_title.strip() == "code" or " - code" in lowered_title:
        return False

    if any(keyword in lowered for keyword in EXCLUDED_POPUP_WINDOW_KEYWORDS):
        return False

    try:
        descendants = window.descendants()
    except Exception:
        descendants = []

    joined_text = lowered
    button_texts = []
    has_list_like_control = False

    for element in descendants[:150]:
        try:
            text = f"{element.window_text() or ''} {element.element_info.name or ''}".lower().strip()
        except Exception:
            text = ""

        try:
            control_type = element.element_info.control_type or ""
        except Exception:
            control_type = ""

        if text:
            joined_text += f" {text}"

        if control_type in {"List", "ListItem", "DataItem", "Table"}:
            has_list_like_control = True

        if control_type == "Button" and text:
            button_texts.append(text)

    strong_signals = [
        "seleccionar un certificado",
        "información del certificado",
        "informacion del certificado",
        "informaciã³n del certificado",
        "necesita sus credenciales",
        "lista de certificados",
    ]

    has_strong_text_signal = any(signal in joined_text for signal in strong_signals)
    has_certificate_word = any(signal in joined_text for signal in ["certificado", "certificate", "credenciales"])
    has_accept_button = any("aceptar" in text or "accept" in text for text in button_texts)
    has_cancel_button = any("cancelar" in text or "cancel" in text for text in button_texts)

    evidence_score = sum(
        [
            has_strong_text_signal,
            has_list_like_control,
            has_accept_button,
            has_cancel_button,
        ]
    )

    return (has_certificate_word and evidence_score >= 2) or (has_strong_text_signal and (has_accept_button or has_cancel_button))


def _is_certificate_popup(window):
    return _has_certificate_popup_evidence(window)

    if _is_interesting_window(window):
        try:
            descendants = window.descendants()
        except Exception:
            descendants = []

        joined_text = lowered
        for element in descendants[:100]:
            try:
                text = f"{element.window_text() or ''} {element.element_info.name or ''}".lower()
            except Exception:
                text = ""
            joined_text += f" {text}"

        popup_keywords = [
            "seleccionar un certificado",
            "credenciales",
            "información del certificado",
            "informacion del certificado",
            "certificado",
            "certificate",
        ]
        return any(keyword in joined_text for keyword in popup_keywords)

    try:
        descendants = window.descendants()
    except Exception:
        descendants = []

    for element in descendants[:100]:
        try:
            text = f"{element.window_text() or ''} {element.element_info.name or ''}".lower()
        except Exception:
            text = ""

        if any(keyword in text for keyword in ["certificado", "certificate", "seleccionar un certificado", "credenciales"]):
            return True

    return False


def _log_window_snapshot(backend_name):
    logger.info("popup certificado: snapshot de ventanas backend=%s", backend_name)
    try:
        windows = Desktop(backend=backend_name).windows()
    except Exception as exc:
        logger.warning("popup certificado: no se pudo listar ventanas backend=%s: %s", backend_name, exc)
        return

    for index, window in enumerate(windows[:30]):
        title, class_name, control_type, process_id = _get_window_metadata(window)
        if not title and not _is_interesting_window(window):
            continue
        logger.info(
            "popup certificado: window[%s] title='%s' class='%s' type='%s' pid=%s",
            index,
            title,
            class_name,
            control_type,
            process_id,
        )


def _log_popup_children(popup_window):
    try:
        descendants = popup_window.descendants()
    except Exception as exc:
        logger.warning("popup certificado: no se pudieron leer controles del popup: %s", exc)
        return

    logger.info("popup certificado: controles detectados=%s", len(descendants))
    for index, element in enumerate(descendants[:40]):
        try:
            text = f"{element.window_text() or ''} {element.element_info.name or ''}".strip()
        except Exception:
            text = ""

        try:
            control_type = element.element_info.control_type or ""
        except Exception:
            control_type = ""

        try:
            class_name = element.element_info.class_name or ""
        except Exception:
            class_name = ""

        if not text and not control_type:
            continue

        logger.info(
            "popup certificado: control[%s] type='%s' class='%s' text='%s'",
            index,
            control_type,
            class_name,
            text,
        )


def _click_single_certificate_candidate(popup_window):
    primary_candidates = []
    secondary_candidates = []

    try:
        descendants = popup_window.descendants()
    except Exception:
        descendants = []

    for element in descendants:
        try:
            control_type = element.element_info.control_type or ""
        except Exception:
            control_type = ""

        try:
            text = f"{element.window_text() or ''} {element.element_info.name or ''}".strip()
        except Exception:
            text = ""

        if not text:
            continue

        normalized_text = text.lower()

        if control_type in {"List", "ListItem", "DataItem"}:
            primary_candidates.append((control_type, element, text))
            continue

        if control_type == "CheckBox" and "certificado" in normalized_text:
            primary_candidates.append((control_type, element, text))
            continue

        if control_type == "Text" and any(char.isdigit() for char in text):
            secondary_candidates.append((control_type, element, text))

    candidates = primary_candidates or secondary_candidates

    if len(candidates) == 1:
        control_type, element, text = candidates[0]
        logger.info("popup certificado: seleccionando unica opcion detectada (%s): %s", control_type, text)
        try:
            element.click_input()
            time.sleep(0.5)
            send_keys("{SPACE}")
            time.sleep(0.3)
            return True
        except Exception as exc:
            logger.warning("popup certificado: no se pudo hacer click en la unica opcion: %s", exc)
            try:
                rect = element.rectangle()
                element.click_input(coords=((rect.width() // 2), (rect.height() // 2)))
                time.sleep(0.5)
                send_keys("{SPACE}")
                time.sleep(0.3)
                return True
            except Exception as inner_exc:
                logger.warning("popup certificado: fallo tambien el click centrado: %s", inner_exc)

    logger.info("popup certificado: opciones detectadas=%s", len(candidates))
    return False


def _click_accept_button(popup_window):
    accept_words = {"aceptar", "accept", "ok"}

    try:
        descendants = popup_window.descendants()
    except Exception:
        descendants = []

    for element in descendants:
        try:
            control_type = element.element_info.control_type or ""
        except Exception:
            control_type = ""

        if control_type != "Button":
            continue

        try:
            text = f"{element.window_text() or ''} {element.element_info.name or ''}".lower().strip()
        except Exception:
            text = ""

        if not text:
            continue

        if not any(word in text for word in accept_words):
            continue

        logger.info("popup certificado: pulsando boton de confirmacion '%s'", text)
        try:
            element.click_input()
            return True
        except Exception as exc:
            logger.warning("popup certificado: fallo al pulsar boton '%s': %s", text, exc)

    return False


def _confirm_focused_dialog_with_keyboard():
    logger.info("popup certificado: intentando confirmacion por teclado sobre ventana enfocada")
    send_keys("{TAB}")
    time.sleep(0.3)
    send_keys("{DOWN}")
    time.sleep(0.3)
    send_keys("{ENTER}")
    return True


def _detect_certificate_error_modal(page, error_text_parts):
    check_start = time.perf_counter()
    logger.info("popup certificado: inicio comprobacion modal funcional")

    try:
        error_modal = page.get_by_text(error_text_parts[0], exact=False)
        detected = (
            error_modal.count() > 0
            and error_modal.first.is_visible()
            and page.get_by_text(error_text_parts[1], exact=False).count() > 0
        )
    except Exception:
        detected = False

    logger.info(
        "popup certificado: fin comprobacion modal funcional elapsed=%.2fs detected=%s",
        time.perf_counter() - check_start,
        detected,
    )
    return detected


def _run_with_timeout(operation, timeout_seconds, operation_name, default_value):
    result = {"value": default_value, "completed": False, "error": None}

    def target():
        try:
            result["value"] = operation()
            result["completed"] = True
        except Exception as exc:
            result["error"] = exc

    worker = threading.Thread(target=target, daemon=True)
    worker.start()
    worker.join(timeout_seconds)

    if worker.is_alive():
        logger.warning(
            "popup certificado: operacion '%s' excedio timeout interno=%.2fs; se desactiva comprobacion auxiliar",
            operation_name,
            timeout_seconds,
        )
        return default_value, False

    if result["error"] is not None:
        logger.warning(
            "popup certificado: operacion '%s' fallo: %s",
            operation_name,
            result["error"],
        )
        return default_value, False

    return result["value"], True


def confirm_certificate_popup(page, timeout=20):
    """Detect the native certificate popup or the DEHu certificate error modal."""

    logger.info("esperando popup de certificado timeout=%ss", timeout)
    backends = ["uia", "win32"]
    start_time = time.time()
    start_perf = time.perf_counter()
    snapshot_logged = False
    page_checks_enabled = True
    error_text_parts = [
        "No se ha seleccionado/enviado",
        "Certificado a la plataforma @Firma",
    ]

    while True:
        elapsed = time.perf_counter() - start_perf
        if elapsed >= timeout:
            break

        logger.info("popup certificado: elapsed=%.2fs", elapsed)

        if page_checks_enabled:
            remaining = max(0.1, timeout - elapsed)
            page_closed, page_closed_ok = _run_with_timeout(
                lambda: page.is_closed(),
                min(0.25, remaining),
                "page.is_closed",
                False,
            )
            if not page_closed_ok:
                page_checks_enabled = False
            elif page_closed:
                logger.error("popup certificado: la pagina se cerro durante la espera")
                return "timeout"

        if page_checks_enabled:
            modal_detected, modal_check_ok = _run_with_timeout(
                lambda: _detect_certificate_error_modal(page, error_text_parts),
                min(0.75, max(0.1, timeout - elapsed)),
                "detect_certificate_error_modal",
                False,
            )
            if not modal_check_ok:
                page_checks_enabled = False
            elif modal_detected:
                logger.error("popup certificado: detectado modal web de certificado no enviado")
                return "error_modal_certificado"

        for backend_name in backends:
            if time.perf_counter() - start_perf >= timeout:
                break

            try:
                windows = Desktop(backend=backend_name).windows()
            except Exception:
                windows = []

            for window in windows:
                if not _is_certificate_popup(window):
                    continue

                title, class_name, control_type, process_id = _get_window_metadata(window)
                logger.info(
                    "popup certificado detectado backend=%s title='%s' class='%s' type='%s' pid=%s",
                    backend_name,
                    title,
                    class_name,
                    control_type,
                    process_id,
                )

                try:
                    window.set_focus()
                except Exception:
                    pass

                _log_popup_children(window)
                _click_single_certificate_candidate(window)

                if _click_accept_button(window):
                    logger.info("popup certificado confirmado con boton")
                    return "popup_confirmado"

                logger.warning("popup certificado: popup detectado pero no se pudo confirmar con boton; intentando teclado")
                if _has_certificate_popup_evidence(window) and _confirm_focused_dialog_with_keyboard():
                    logger.info("popup certificado confirmado con teclado")
                    return "popup_confirmado"

        if not snapshot_logged and int(time.time() - start_time) >= 3 and (time.perf_counter() - start_perf) < timeout:
            for backend_name in backends:
                snapshot_start = time.perf_counter()
                logger.info(
                    "popup certificado: inicio snapshot de ventanas backend=%s elapsed=%.2fs",
                    backend_name,
                    time.perf_counter() - start_perf,
                )
                _log_window_snapshot(backend_name)
                logger.info(
                    "popup certificado: fin snapshot de ventanas backend=%s elapsed=%.2fs snapshot_duration=%.2fs",
                    backend_name,
                    time.perf_counter() - start_perf,
                    time.perf_counter() - snapshot_start,
                )
            snapshot_logged = True

        remaining = timeout - (time.perf_counter() - start_perf)
        if remaining <= 0:
            break
        time.sleep(min(0.5, remaining))

    if page_checks_enabled:
        modal_detected, modal_check_ok = _run_with_timeout(
            lambda: _detect_certificate_error_modal(page, error_text_parts),
            0.75,
            "detect_certificate_error_modal_final",
            False,
        )
        if modal_check_ok and modal_detected:
            logger.error(
                "popup certificado: modal funcional detectado al finalizar timeout total=%.2fs",
                time.perf_counter() - start_perf,
            )
            return "error_modal_certificado"

    logger.error(
        "popup certificado no detectado dentro del timeout total=%.2fs",
        time.perf_counter() - start_perf,
    )
    return "timeout"


def start_login(page):
    """Navigate to the certificate step without validating the authenticated state."""

    logger.info("navegacion DEHu")
    page.goto("https://dehu.redsara.es/es/public")

    logger.info("Waiting for DEHu access button")
    access_button = page.locator("button").filter(has_text=re.compile(r"Acceder\s+a\s+DEH", re.IGNORECASE)).first
    access_button.wait_for(timeout=30000)

    logger.info('click en "Acceder a DEHu"')
    access_button.click()

    logger.info("Waiting for certificate access button")
    certificate_button = page.locator("button").filter(
        has_text=re.compile(r"Acceso\s+DNIe\s*/\s*Certificado", re.IGNORECASE)
    ).first
    certificate_button.wait_for(timeout=30000)

    logger.info('click en "Acceso DNIe / Certificado"')
    certificate_button.click()


def validate_login(page, timeout=60):
    """Return the authenticated DEHu page when login completes successfully."""

    logger.info("validando login")
    start_time = time.time()
    last_logged_slot = None

    while time.time() - start_time < timeout:
        context_pages = []
        try:
            context_pages = list(page.context.pages)
        except Exception:
            context_pages = [page]

        ordered_pages = []
        seen_ids = set()
        for candidate in [page] + context_pages:
            candidate_id = id(candidate)
            if candidate_id in seen_ids:
                continue
            seen_ids.add(candidate_id)
            ordered_pages.append(candidate)

        current_slot = int(time.time() - start_time) // 5
        for index, candidate in enumerate(ordered_pages):
            try:
                candidate_url = candidate.url
            except Exception:
                candidate_url = "<url no disponible>"

            if current_slot != last_logged_slot:
                logger.info("validando login: page[%s] url=%s", index, candidate_url)

            if "dehu.redsara.es" in candidate_url and "/home-view" in candidate_url:
                try:
                    candidate.wait_for_load_state("domcontentloaded", timeout=5000)
                except Exception:
                    pass
                candidate.bring_to_front()
                logger.info("login correcto")
                return candidate

            try:
                locator = candidate.locator("a").filter(
                    has_text=re.compile(r"Datos\s+de\s+contacto", re.IGNORECASE)
                ).first
                locator.wait_for(timeout=1000)
                candidate.bring_to_front()
                logger.info("login correcto")
                return candidate
            except Exception:
                pass

        last_logged_slot = current_slot
        time.sleep(1)

    logger.error("login incorrecto o no validado dentro del timeout")
    return None


def alta_destinatario(page, cliente):
    logger.info("Opening 'Datos de contacto'")
    logger.info("alta destinatario: url actual=%s", page.url)

    try:
        page.wait_for_load_state("domcontentloaded", timeout=10000)
    except Exception:
        pass

    contact_locators = [
        page.get_by_role("link", name=re.compile(r"Datos\s+de\s+contacto", re.IGNORECASE)),
        page.get_by_role("button", name=re.compile(r"Datos\s+de\s+contacto", re.IGNORECASE)),
        page.locator("text=/Datos\\s+de\\s+contacto/i"),
        page.locator("a,button,span,div").filter(has_text=re.compile(r"Datos\s+de\s+contacto", re.IGNORECASE)),
    ]

    clicked = False
    for index, locator in enumerate(contact_locators):
        try:
            count = locator.count()
        except Exception:
            count = 0

        logger.info("alta destinatario: candidatos 'Datos de contacto' locator[%s]=%s", index, count)
        if count == 0:
            continue

        try:
            locator.first.wait_for(timeout=5000)
            locator.first.click()
            clicked = True
            logger.info("alta destinatario: click realizado sobre 'Datos de contacto' con locator[%s]", index)
            break
        except Exception as exc:
            logger.warning("alta destinatario: fallo con locator[%s]: %s", index, exc)

    if not clicked:
        logger.error("alta destinatario: no se encontro un selector util para 'Datos de contacto'")
        return "error"

    correo_locator = None
    add_email_visible = False
    verify_visible = False
    email_card_visible = False

    for attempt in range(10):
        logger.info("alta destinatario: inspeccion bloque correo intento=%s", attempt + 1)

        correo_input_locators = [
            page.get_by_role("textbox", name=re.compile(r"Correo", re.IGNORECASE)),
            page.get_by_placeholder(re.compile(r"Escribe\s+el\s+correo", re.IGNORECASE)),
            page.locator("input[placeholder*='correo' i]"),
            page.locator("input[type='text'], input[type='email'], textarea"),
        ]

        for index, locator in enumerate(correo_input_locators):
            try:
                count = locator.count()
            except Exception:
                count = 0

            logger.info("alta destinatario: candidatos campo correo locator[%s]=%s", index, count)
            if count == 0:
                continue

            for candidate_index in range(count):
                try:
                    candidate = locator.nth(candidate_index)
                    if candidate.is_visible() and candidate.is_enabled():
                        correo_locator = candidate
                        logger.info(
                            "alta destinatario: campo correo localizado con locator[%s]/candidate[%s]",
                            index,
                            candidate_index,
                        )
                        break
                except Exception:
                    continue

            if correo_locator is not None:
                break

        if correo_locator is not None:
            break

        signal_locators = [
            page.locator("text=/A[nñ]adir\\s+correo\\s+electr[oó]nico/i"),
            page.locator("text=/Verificar/i"),
            page.locator("text=/Correo\\s+electr[oó]nico\\s+1/i"),
            page.locator("text=/[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}/i"),
        ]

        try:
            add_email_visible = signal_locators[0].count() > 0 and signal_locators[0].first.is_visible()
        except Exception:
            add_email_visible = False

        try:
            verify_visible = signal_locators[1].count() > 0 and signal_locators[1].first.is_visible()
        except Exception:
            verify_visible = False

        try:
            email_card_visible = (
                (signal_locators[2].count() > 0 and signal_locators[2].first.is_visible())
                or (signal_locators[3].count() > 0 and signal_locators[3].first.is_visible())
            )
        except Exception:
            email_card_visible = False

        logger.info(
            "alta destinatario: add_email_visible=%s verify_visible=%s email_card_visible=%s",
            add_email_visible,
            verify_visible,
            email_card_visible,
        )

        if verify_visible and email_card_visible:
            logger.warning("campo correo no disponible y ya existe un email configurado; posible cliente ya dado de alta")
            return "ya_dado_de_alta"

        page.wait_for_timeout(1000)

    if correo_locator is None:
        if add_email_visible:
            logger.error("alta destinatario: hay UI de alta disponible pero no se encontro el input de correo")
            return "error"

        logger.error("alta destinatario: no se pudo clasificar el estado del bloque de correo")
        return "error"

    logger.info("Filling contact email for client %s", cliente.nif)
    try:
        correo_locator.fill(cliente.email)
        logger.info("campo correo disponible y rellenado correctamente")
    except Exception as exc:
        logger.error("alta destinatario: error rellenando el campo correo: %s", exc)
        return "error"

    logger.info("Accepting notification checkbox and saving")
    try:
        page.locator(".dnt-checkbox__inner").click()
        page.get_by_role("button", name="Guardar").click()
        page.wait_for_timeout(5000)
        return "alta_realizada"
    except Exception as exc:
        logger.error("alta destinatario: error guardando datos de contacto: %s", exc)
        return "error"


def cerrar_sesion(page):
    logger.info("Closing DEHu session")

    logout_locators = [
        page.get_by_role("link", name=re.compile(r"Cerrar\s+sesion|Cerrar\s+sesión", re.IGNORECASE)),
        page.get_by_role("button", name=re.compile(r"Cerrar\s+sesion|Cerrar\s+sesión", re.IGNORECASE)),
        page.locator("text=/Cerrar\\s+sesi[oó]n/i"),
    ]

    for index, locator in enumerate(logout_locators):
        try:
            if locator.count() > 0:
                locator.first.click()
                logger.info("logout: click directo en 'Cerrar sesion' con locator[%s]", index)
                return True
        except Exception as exc:
            logger.warning("logout: fallo en click directo locator[%s]: %s", index, exc)

    menu_locators = [
        page.locator("header [aria-haspopup='menu']"),
        page.locator("header button"),
        page.locator("[aria-haspopup='menu']"),
        page.locator("[role='button']").filter(has_not_text=re.compile(r"Guardar|Cancelar", re.IGNORECASE)),
    ]

    for index, locator in enumerate(menu_locators):
        try:
            count = locator.count()
        except Exception:
            count = 0

        logger.info("logout: candidatos menu usuario locator[%s]=%s", index, count)
        if count == 0:
            continue

        try:
            locator.last.click()
            page.wait_for_timeout(1000)
        except Exception as exc:
            logger.warning("logout: no se pudo abrir el menu con locator[%s]: %s", index, exc)
            continue

        for logout_index, logout_locator in enumerate(logout_locators):
            try:
                if logout_locator.count() == 0:
                    continue
                logout_locator.first.click()
                logger.info(
                    "logout: click en 'Cerrar sesion' tras abrir menu locator[%s] con logout locator[%s]",
                    index,
                    logout_index,
                )
                return True
            except Exception as exc:
                logger.warning(
                    "logout: fallo al pulsar 'Cerrar sesion' tras abrir menu locator[%s]/logout[%s]: %s",
                    index,
                    logout_index,
                    exc,
                )

    logger.error("logout: no se pudo cerrar la sesion")
    return False


def cerrar_sesion_simple(page):
    logger.info("Closing DEHu session")

    logout_locators = [
        page.get_by_role("link", name=re.compile(r"Cerrar\s+sesion|Cerrar\s+sesi[oó]n", re.IGNORECASE)),
        page.get_by_role("button", name=re.compile(r"Cerrar\s+sesion|Cerrar\s+sesi[oó]n", re.IGNORECASE)),
        page.locator("text=/Cerrar\\s+sesi[oó]n/i"),
    ]

    for index, locator in enumerate(logout_locators):
        try:
            if locator.count() > 0 and locator.first.is_visible():
                locator.first.click(force=True)
                logger.info("logout: click directo en 'Cerrar sesion' con locator[%s]", index)
                return True
        except Exception as exc:
            logger.warning("logout: fallo en click directo locator[%s]: %s", index, exc)

    menu_locators = [
        page.locator("[aria-haspopup='menu']"),
        page.locator("[aria-expanded]"),
    ]

    for index, locator in enumerate(menu_locators):
        try:
            count = locator.count()
        except Exception:
            count = 0

        logger.info("logout: candidatos menu usuario locator[%s]=%s", index, count)
        if count == 0:
            continue

        for candidate_index in range(count):
            try:
                candidate = locator.nth(candidate_index)
                try:
                    candidate_text = candidate.inner_text(timeout=1000).strip()
                except Exception:
                    candidate_text = "<sin texto>"

                logger.info(
                    "logout: probando menu locator[%s]/candidate[%s] text='%s'",
                    index,
                    candidate_index,
                    candidate_text,
                )
                candidate.click(force=True)
                page.wait_for_timeout(800)
            except Exception as exc:
                logger.warning(
                    "logout: no se pudo abrir el menu locator[%s]/candidate[%s]: %s",
                    index,
                    candidate_index,
                    exc,
                )
                continue

            for logout_index, logout_locator in enumerate(logout_locators):
                try:
                    if logout_locator.count() == 0 or not logout_locator.first.is_visible():
                        continue
                    logout_locator.first.click(force=True)
                    logger.info(
                        "logout: click en 'Cerrar sesion' tras abrir menu locator[%s]/candidate[%s] con logout locator[%s]",
                        index,
                        candidate_index,
                        logout_index,
                    )
                    return True
                except Exception as exc:
                    logger.warning(
                        "logout: fallo al pulsar 'Cerrar sesion' tras abrir menu locator[%s]/candidate[%s]/logout[%s]: %s",
                        index,
                        candidate_index,
                        logout_index,
                        exc,
                    )

    logger.error("logout: no se pudo cerrar la sesion")
    return False


def cerrar_sesion_perfil(page):
    logger.info("Closing DEHu session")

    try:
        page.wait_for_load_state("domcontentloaded", timeout=3000)
    except Exception:
        pass

    page.wait_for_timeout(1000)

    profile_menu_candidates = [
        page.locator("[aria-haspopup='menu']").first,
        page.locator("[aria-expanded]").first,
    ]

    logout_locators = [
        page.get_by_role("link", name=re.compile(r"Cerrar\s+sesion|Cerrar\s+sesi[oó]n", re.IGNORECASE)),
        page.get_by_role("button", name=re.compile(r"Cerrar\s+sesion|Cerrar\s+sesi[oó]n", re.IGNORECASE)),
        page.locator("text=/Cerrar\\s+sesi[oó]n/i"),
    ]

    for index, menu_locator in enumerate(profile_menu_candidates):
        try:
            logger.info("logout: abriendo menu de perfil con candidate[%s]", index)
            menu_locator.click(force=True)
            page.wait_for_timeout(1200)
        except Exception as exc:
            logger.warning("logout: no se pudo abrir el menu de perfil candidate[%s]: %s", index, exc)
            continue

        for logout_index, logout_locator in enumerate(logout_locators):
            try:
                if logout_locator.count() == 0 or not logout_locator.first.is_visible():
                    continue
                logout_locator.first.click(force=True)
                logger.info(
                    "logout: click en 'Cerrar sesion' con candidate[%s] y logout locator[%s]",
                    index,
                    logout_index,
                )
                return True
            except Exception as exc:
                logger.warning(
                    "logout: fallo al pulsar 'Cerrar sesion' con candidate[%s]/logout[%s]: %s",
                    index,
                    logout_index,
                    exc,
                )

    logger.error("logout: no se pudo cerrar la sesion")
    return False
