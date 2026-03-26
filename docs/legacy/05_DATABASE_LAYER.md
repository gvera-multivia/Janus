# Capa de Base de Datos

## Motor y patrón

La persistencia principal usa SQL Server vía `pymssql`.

Hay una clase base, `DatabaseManager`, y especializaciones por dominio:

- `AltasDatabase`
- `DescargaDatabase`
- `ConsultasDatabase`
- `InformesDgtDatabase`
- `SedeJudicialDatabase`

## `DatabaseManager`

Responsabilidades:

- abrir conexión con soporte `host:port`
- gestionar logging
- reintentar deadlocks con `retry_on_deadlock`
- insertar/actualizar histórico
- recuperar histórico por fecha
- insertar/eliminar registros de asignación funcional

## Tablas conceptualmente centrales

- `historico_automatizaciones`
- `automations_assignment_log`
- `emails_messages`
- `certificates_managements_`
- `certificates_sedes`

## Asignación funcional

Además de la asignación técnica vía Redis, existe `automations_assignment_log`.

IDs típicos:

- `alta_{cliente}_{sede}`
- `informedgt_{cliente}_{sede}`
- `consulta_{cliente}_{sede}`
- `{message_key}`
- `{cliente}_sedejudicial`

## Especialización por dominio

### Altas

- `fetch_altas`
- `assign_certificates`
- `unassign_certificate`
- `update_alta_status`
- `update_certificate_alert`

### Descargas

- `fetch_notifications`
- `assign_notifications`
- `update_notification_status`
- `update_historico_descarga`

### Consulta eNotum

- consulta de clientes
- extracción de notificaciones por fecha
- actualización del resultado de consulta

### Informes DGT

- `fetch_dev_clientes`
- `ensure_column_exists`
- `insert_matriculas`
- `insert_puntos`

### Sede Judicial

- `fetch_sedejudicial`
- `update_historico_sedejudicial`

## Riesgos

- SQL incrustado en strings largos repartidos entre código y `queries/`.
- Parte del modelo de datos está implícita en la lógica de persistencia.
- Algunos métodos hacen `commit` repetidos dentro de bucles.
