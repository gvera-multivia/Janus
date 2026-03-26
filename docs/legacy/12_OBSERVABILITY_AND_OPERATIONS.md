# Observabilidad y Operación

## Fuentes de observabilidad

### Logs

Cada dominio escribe en `logs/<modulo>` mediante `LoggerV2`.

Módulos visibles:

- `api`
- `altas`
- `descargas`
- `consultaenotum`
- `matriculasypuntos`
- `sedejudicial`

### Status API

`api/routes/status.py` reconstruye el estado con:

- `Inspect` de Celery
- claves Redis
- cola del dispatcher

### History API

`api/routes/history.py` expone histórico por fecha desde SQL Server.

### Logs API

`api/routes/logs.py` permite:

- listar árbol de logs
- ver último log global
- ver último log por módulo
- buscar log por módulo y `task_id`
- ver tail de logs API

## Qué mirar cuando algo falla

1. `GET /api/system/status`
2. `GET /api/system/progress/{task_id}`
3. `GET /api/logs/view/{module}/{task_id}`
4. histórico SQL si hubo persistencia parcial
5. Redis para `worker_status:*`, `task_registry:*`, `task_progress:*`

## Tipos de fallo frecuentes

- worker sin heartbeat
- tarea asignada pero rechazada
- tarea atascada en `PENDING`
- popup de certificado no encontrado
- certificado caducado o revocado
- error SQL o deadlock
- portal con cambio de HTML o flujo

## Readiness real del sistema

El sistema está sano solo si se cumplen a la vez:

- API levantada
- Redis accesible
- al menos un worker vivo
- escritorio del worker disponible
- RedTrust funcional
- SQL Server accesible
- certificados vigentes
