from browser.edge_browser import start_browser
from certificates.redtrust_bridge import select_certificate
from core.results import build_process_result, capture_web_evidence
from dehu.dehu_automation import (
    alta_destinatario,
    cerrar_sesion_perfil,
    confirm_certificate_popup,
    start_login,
    validate_login,
)
from utils.logger import get_logger

logger = get_logger()

RUN_REDTRUST = True
AUTO_CONFIRM_CERTIFICATE_POPUP = True
LOGIN_TIMEOUT_SECONDS = 60


def process_client(cliente):
    playwright = None
    browser = None
    page = None

    try:
        if RUN_REDTRUST:
            logger.info("inicio Redtrust para cliente %s", cliente.nif)
            redtrust_ok = select_certificate(cliente.id_redtrust, mode="full")
            if not redtrust_ok:
                logger.error("fin Redtrust KO para cliente %s", cliente.nif)
                return build_process_result(
                    "error_redtrust",
                    "error en la preseleccion del certificado en Redtrust",
                    "redtrust",
                )

            logger.info("fin Redtrust OK para cliente %s", cliente.nif)
        else:
            logger.info("inicio Redtrust omitido (modo pruebas popup) para cliente %s", cliente.nif)
            logger.info("fin Redtrust OK (omitido) para cliente %s", cliente.nif)

        logger.info("lanzamiento Edge para cliente %s", cliente.nif)
        try:
            playwright, browser, context, page = start_browser(cliente)
        except Exception:
            logger.exception("error en Edge para cliente %s", cliente.nif)
            url_error, captura_error = capture_web_evidence(page, cliente, "edge")
            return build_process_result(
                "error_edge",
                "error al lanzar o conectar Edge/Playwright",
                "edge",
                url_error,
                captura_error,
            )

        logger.info("puerto remoto listo para cliente %s", cliente.nif)
        logger.info("Playwright conectado para cliente %s", cliente.nif)

        start_login(page)

        if AUTO_CONFIRM_CERTIFICATE_POPUP:
            popup_result = confirm_certificate_popup(page, timeout=20)
            if popup_result == "error_modal_certificado":
                logger.error("modal web de certificado no enviado para cliente %s", cliente.nif)
                url_error, captura_error = capture_web_evidence(page, cliente, "popup_certificado")
                return build_process_result(
                    "error_certificado_invalido",
                    "DEHU mostro el error: no se ha seleccionado/enviado ningun Certificado a la plataforma @Firma",
                    "certificado_invalido",
                    url_error,
                    captura_error,
                )
            if popup_result != "popup_confirmado":
                logger.error("popup de certificado KO para cliente %s", cliente.nif)
                url_error, captura_error = capture_web_evidence(page, cliente, "popup_certificado")
                return build_process_result(
                    "popup_no_detectado",
                    "no se encontro o no se automatizo un popup valido de certificado en Edge/Cl@ve",
                    "popup_certificado",
                    url_error,
                    captura_error,
                )
        else:
            logger.info("esperando seleccion manual de certificado para cliente %s", cliente.nif)
            input("Selecciona el certificado en el popup y pulsa Enter para continuar...")
            logger.info("reanundando tras seleccion manual para cliente %s", cliente.nif)

        authenticated_page = validate_login(page, timeout=LOGIN_TIMEOUT_SECONDS)
        if authenticated_page is None:
            logger.error("login KO para cliente %s", cliente.nif)
            url_error, captura_error = capture_web_evidence(page, cliente, "login")
            return build_process_result(
                "error_login",
                "no se pudo validar el login en DEHU",
                "login",
                url_error,
                captura_error,
            )

        alta_result = alta_destinatario(authenticated_page, cliente)

        logout_ok = cerrar_sesion_perfil(authenticated_page)
        if not logout_ok:
            logger.error("logout KO para cliente %s", cliente.nif)
            url_error, captura_error = capture_web_evidence(authenticated_page, cliente, "logout")
            return build_process_result(
                "error_logout",
                "no se pudo cerrar la sesion de DEHU",
                "logout",
                url_error,
                captura_error,
            )

        if alta_result == "alta_realizada":
            return build_process_result("alta_realizada", "alta realizada correctamente")
        if alta_result == "ya_dado_de_alta":
            return build_process_result("cliente_ya_dado_de_alta", "cliente ya dado de alta")

        url_error, captura_error = capture_web_evidence(authenticated_page, cliente, "alta_destinatario")
        return build_process_result(
            "error_alta",
            "error durante el alta del destinatario",
            "alta_destinatario",
            url_error,
            captura_error,
        )
    except Exception:
        logger.exception("error inesperado procesando cliente %s", getattr(cliente, "nif", "<sin_nif>"))
        url_error, captura_error = capture_web_evidence(page, cliente, "inesperado")
        return build_process_result(
            "error_inesperado",
            "error inesperado durante el procesamiento del cliente",
            "inesperado",
            url_error,
            captura_error,
        )
    finally:
        if browser is not None:
            browser.close()
        if playwright is not None:
            playwright.stop()
