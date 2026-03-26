import re
from datetime import datetime
from time import perf_counter

from core.results import build_process_result, build_result_entry
from models.cliente import Cliente
from utils.logger import get_logger

logger = get_logger()

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_client_data(raw_client):
    if not isinstance(raw_client, dict):
        return False

    nif = str(raw_client.get("nif", "")).strip()
    email = str(raw_client.get("email", "")).strip()
    id_redtrust = str(raw_client.get("id_redtrust", "")).strip()

    if not nif:
        return False

    if not id_redtrust:
        return False

    if not email or not EMAIL_PATTERN.match(email):
        return False

    return True


def build_cliente(raw_client):
    return Cliente(
        nif=str(raw_client.get("nif", "")).strip(),
        nombre=str(raw_client.get("nombre", "")).strip(),
        email=str(raw_client.get("email", "")).strip(),
        id_redtrust=str(raw_client.get("id_redtrust", "")).strip(),
    )


def run_client_batch(raw_clients, attempt_number, process_client_fn, job_id=None, sede=None):
    results = []

    for index, raw_client in enumerate(raw_clients, start=1):
        logger.info("procesando cliente intento %s - %s/%s", attempt_number, index, len(raw_clients))
        timestamp_inicio = datetime.now().isoformat(timespec="seconds")
        start_counter = perf_counter()

        if not validate_client_data(raw_client):
            logger.error("cliente con datos invalidos; se registra error_datos_entrada")
            timestamp_fin = datetime.now().isoformat(timespec="seconds")
            results.append(
                build_result_entry(
                    raw_client,
                    build_process_result(
                        "error_datos_entrada",
                        "datos de entrada invalidos para el cliente",
                        "validacion_entrada",
                        None,
                        None,
                    ),
                    timestamp_inicio,
                    timestamp_fin,
                    perf_counter() - start_counter,
                    intento=attempt_number,
                    job_id=job_id,
                    sede=sede,
                )
            )
            continue

        cliente = build_cliente(raw_client)
        process_result = process_client_fn(cliente)
        timestamp_fin = datetime.now().isoformat(timespec="seconds")
        results.append(
            build_result_entry(
                cliente,
                process_result,
                timestamp_inicio,
                timestamp_fin,
                perf_counter() - start_counter,
                intento=attempt_number,
                job_id=job_id,
                sede=sede,
            )
        )

    return results
