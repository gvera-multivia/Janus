# Redis y Estado Runtime

## Papel de Redis

Redis cumple cuatro funciones:

- broker/backend de Celery
- cola de entrada del dispatcher
- almacén efímero de heartbeats y progreso
- mecanismo de bloqueo/asignación de tareas

## Claves principales

### `dispatcher_tasks_queue`

Lista Redis con tareas todavía no asignadas a ningún worker.

### `worker_status:{worker_id}`

JSON con heartbeat y telemetría del worker:

- IP
- hostname
- usuario
- estado lógico
- tarea actual
- CPU, RAM, disco, red
- PID y uptime

TTL: 30 segundos.

### `task_registry:{worker_id}`

Hash con el registro de tareas arrancadas en ese worker.

### `task_progress:{task_id}`

JSON con progreso vivo de la tarea.

### `task_assignment:{task_id}`

Lock lógico de asignación con expiración.

### `celery-task-meta-{task_id}`

Metadatos nativos de Celery.

## `RedisManager`

`api/redis.py` centraliza:

- `register_task_start`
- `publish_task_progress`
- `register_task_end`
- `assign_task`
- `get_task_assignment`
- `clear_task_assignment`

## Cómo se reconstruye el estado

`api/routes/status.py` mezcla:

- `Inspect` de Celery
- heartbeats en Redis
- `dispatcher_tasks_queue`
- `task_registry:*`
- `task_progress:*`

para reconstruir workers y tareas.

## Limitaciones

- El estado es parcialmente eventual.
- Si Redis pierde datos efímeros, se degrada la monitorización aunque la tarea siga viva.
- Puede haber desalineación entre histórico SQL, registry Redis y backend Celery.
