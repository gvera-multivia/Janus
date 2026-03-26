import json
from datetime import datetime
from pathlib import Path


def load_job_from_json(path):
    with Path(path).open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError("El archivo de job debe contener un objeto JSON")

    job_id = str(data.get("job_id", "")).strip()
    sede = str(data.get("sede", "")).strip().lower()
    clientes = data.get("clientes")

    if not job_id:
        raise ValueError("El job debe incluir 'job_id'")

    if not sede:
        raise ValueError("El job debe incluir 'sede'")

    if not isinstance(clientes, list):
        raise ValueError("El job debe incluir 'clientes' como lista")

    return {
        "job_id": job_id,
        "sede": sede,
        "clientes": clientes,
    }


def build_legacy_local_job(clientes):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return {
        "job_id": f"local_dehu_{timestamp}",
        "sede": "dehu",
        "clientes": clientes,
    }

