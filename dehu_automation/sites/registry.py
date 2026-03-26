from sites.dehu.site import process_client as process_dehu_client


SITE_PROCESSORS = {
    "dehu": process_dehu_client,
}


def get_site_processor(sede):
    normalized = str(sede).strip().lower()

    if normalized not in SITE_PROCESSORS:
        raise ValueError(f"Sede no soportada: {sede}")

    return SITE_PROCESSORS[normalized]

