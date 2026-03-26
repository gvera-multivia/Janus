import json
import sys
from pathlib import Path

from core.job import build_legacy_local_job, load_job_from_json
from core.runner import run_client_batch
from sites.registry import get_site_processor
from utils.logger import get_logger

logger = get_logger()

CLIENTS_JSON_PATH = Path("clientes.json")
RESULTS_JSON_PATH = Path("resultados_clientes.json")
RETRYABLE_RESULTS = {"error_edge", "error_login", "error_inesperado"}


def load_clients_from_json(path):
    with Path(path).open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError("El archivo de clientes debe contener una lista JSON")

    return data


def save_results_to_json(results, path):
    with Path(path).open("w", encoding="utf-8") as file:
        json.dump(results, file, ensure_ascii=False, indent=2)


def print_summary(results):
    total = len(results)
    altas_realizadas = sum(1 for item in results if item["resultado"] == "alta_realizada")
    ya_dados_de_alta = sum(1 for item in results if item["resultado"] == "cliente_ya_dado_de_alta")
    errores_datos = sum(1 for item in results if item["resultado"] == "error_datos_entrada")
    otros_errores = total - altas_realizadas - ya_dados_de_alta - errores_datos

    logger.info("resumen final:")
    logger.info("total clientes: %s", total)
    logger.info("altas realizadas: %s", altas_realizadas)
    logger.info("ya dados de alta: %s", ya_dados_de_alta)
    logger.info("errores de datos: %s", errores_datos)
    logger.info("otros errores: %s", otros_errores)


def main():
    if len(sys.argv) > 1:
        job_path = sys.argv[1]
        job = load_job_from_json(job_path)
        logger.info("ejecutando job local desde %s", job_path)
    else:
        raw_clients = load_clients_from_json(CLIENTS_JSON_PATH)
        job = build_legacy_local_job(raw_clients)
        logger.info("ejecutando modo legacy con clientes.json como job local job_id=%s", job["job_id"])

    job_id = job["job_id"]
    sede = job["sede"]
    raw_clients = job["clientes"]
    process_site_client = get_site_processor(sede)

    logger.info("job_id=%s sede=%s clientes=%s", job_id, sede, len(raw_clients))

    results = run_client_batch(
        raw_clients,
        attempt_number=1,
        process_client_fn=process_site_client,
        job_id=job_id,
        sede=sede,
    )

    retry_clients = [
        raw_client
        for raw_client, result in zip(raw_clients, results)
        if result["resultado"] in RETRYABLE_RESULTS
    ]

    if retry_clients:
        logger.info("iniciando segunda pasada para %s clientes reintentables", len(retry_clients))
        retry_results = run_client_batch(
            retry_clients,
            attempt_number=2,
            process_client_fn=process_site_client,
            job_id=job_id,
            sede=sede,
        )
        results.extend(retry_results)

    save_results_to_json(results, RESULTS_JSON_PATH)
    print_summary(results)


if __name__ == "__main__":
    main()
