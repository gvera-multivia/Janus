# Superficie API

## Router raíz

La API se monta bajo `/api` en `api/server.py`.

Routers incluidos:

- `websocket_backend`
- `altas`
- `descargas`
- `matriculas`
- `reports`
- `status`
- `history`
- `consultaenotum`
- `database`
- `logs`

## Endpoint transversal

### `POST /api/enqueue_task`

Entrada genérica para encolar cualquier tarea registrada.

Payload:

```json
{
  "task_name": "run_robot_descargas",
  "args": [],
  "kwargs": {}
}
```

## Endpoints por dominio

### Altas

- `GET /api/altas`
- `POST /api/altas/trigger`

Encola `run_robot_altas`.

### Descargas

- `GET /api/descargas`
- `POST /api/descargas/trigger`

Requiere `fecha` o `date` y encola `run_robot_descargas`.

### Matrículas

`api/routes/matriculas.py` expone el patrón equivalente para `run_robot_matriculas`.

### Consulta eNotum

`api/routes/consultaenotum.py` expone el patrón equivalente para `run_robot_consulta_enotum`.

### Reports

- `POST /api/reports/generate`

Actualmente es placeholder funcional.

### History

- `GET /api/history/by-date?fecha_descarga=YYYY-MM-DD`

### Database

Router operativo para consultas auxiliares de negocio, incluyendo `descargaespecial`, datos de cliente y avisos.

### Status

Router crítico de operación:

- `GET /api/system/status`
- `GET /api/system/progress/{task_id}`
- `POST /api/system/kill-task/{task_id}`
- endpoints de limpieza y consulta auxiliares

### Logs

- `GET /api/logs/tree`
- `GET /api/logs/view`
- `GET /api/logs/view/{module}`
- `GET /api/logs/view/{module}/{task_id}`
- `GET /api/logs/api`

## Rasgos de diseño de la API

- La API es control-plane: casi nunca hace el trabajo, sino que lo deriva.
- Hay endpoints de negocio y endpoints de operación en el mismo proceso.
- La validación es pragmática y desigual según el endpoint.
