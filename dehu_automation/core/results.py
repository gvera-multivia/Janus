from datetime import datetime
from pathlib import Path

from models.cliente import Cliente
from utils.logger import get_logger

logger = get_logger()

ERROR_ARTIFACTS_DIR = Path("artifacts/errores")


def build_process_result(resultado, mensaje, fase_error=None, url_error=None, captura_error=None):
    return {
        "resultado": resultado,
        "mensaje": mensaje,
        "fase_error": fase_error,
        "url_error": url_error,
        "captura_error": captura_error,
    }


def capture_web_evidence(page, cliente, fase_error):
    url_error = None
    captura_error = None

    if page is None:
        return url_error, captura_error

    try:
        url_error = page.url
    except Exception as exc:
        logger.warning("no se pudo leer la URL de error para cliente %s: %s", cliente.nif, exc)

    try:
        ERROR_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        screenshot_path = ERROR_ARTIFACTS_DIR / f"{cliente.nif}_{timestamp}_{fase_error}.png"
        page.screenshot(path=str(screenshot_path), full_page=True)
        captura_error = str(screenshot_path)
    except Exception as exc:
        logger.warning("no se pudo guardar captura de error para cliente %s: %s", cliente.nif, exc)

    return url_error, captura_error


def build_result_entry(
    cliente,
    process_result,
    timestamp_inicio,
    timestamp_fin,
    duracion_segundos,
    intento=1,
    job_id=None,
    sede=None,
):
    if isinstance(cliente, Cliente):
        return {
            "job_id": job_id,
            "sede": sede,
            "nif": cliente.nif,
            "nombre": cliente.nombre,
            "email": cliente.email,
            "id_redtrust": cliente.id_redtrust,
            "intento": intento,
            "resultado": process_result["resultado"],
            "mensaje": process_result["mensaje"],
            "timestamp_inicio": timestamp_inicio,
            "timestamp_fin": timestamp_fin,
            "duracion_segundos": round(duracion_segundos, 2),
            "fase_error": process_result["fase_error"],
            "url_error": process_result["url_error"],
            "captura_error": process_result["captura_error"],
        }

    return {
        "job_id": job_id,
        "sede": sede,
        "nif": str(cliente.get("nif", "")),
        "nombre": str(cliente.get("nombre", "")),
        "email": str(cliente.get("email", "")),
        "id_redtrust": str(cliente.get("id_redtrust", "")),
        "intento": intento,
        "resultado": process_result["resultado"],
        "mensaje": process_result["mensaje"],
        "timestamp_inicio": timestamp_inicio,
        "timestamp_fin": timestamp_fin,
        "duracion_segundos": round(duracion_segundos, 2),
        "fase_error": process_result["fase_error"],
        "url_error": process_result["url_error"],
        "captura_error": process_result["captura_error"],
    }

