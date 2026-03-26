# Orquestación de Tareas

## Flujo completo

1. Un endpoint o el scheduler llama a `enqueue_task`.
2. `enqueue_task` valida contra `get_robot_tasks()` y hace `RPUSH` en `dispatcher_tasks_queue`.
3. El dispatcher consume esa cola.
4. El dispatcher obtiene workers vivos mediante `Inspect(active)` + heartbeat Redis.
5. Filtra workers con estado `Free`.
6. Escoge el mejor por score.
7. Reserva `task_assignment:{task_id}` en Redis.
8. Publica la tarea real en Celery (`queue='robot_tasks'`).
9. El worker la recibe y verifica si su `worker_id` coincide con la asignación Redis.
10. Si coincide, ejecuta; si no, rechaza la tarea.

## Encolado

`api/enqueuer.py` encapsula la entrada a la cola del dispatcher.

Formato:

```json
{
  "task": "run_robot_descargas",
  "args": [],
  "kwargs": {},
  "timestamp": 1710000000,
  "enqueued_by": "api"
}
```

## Dispatcher

`api/dispatcher.py`:

- descubre workers vivos
- recupera heartbeat y métricas
- decide disponibilidad
- escoge worker por heurística
- reserva asignación
- envía tarea Celery
- registra histórico de asignación

## Heurística de selección

`select_best_worker` usa:

- menos CPU = mejor
- menos memoria = mejor
- menos carga reciente = mejor

No hay afinidad por portal o especialización por worker.

## Workers

`api/worker.py` define `CeleryWorker`.

Tareas registradas:

- `run_robot_altas`
- `run_robot_descargas`
- `run_robot_matriculas`
- `run_robot_consulta_enotum`

## Patrón de rechazo

Antes de ejecutar, cada task consulta `task_assignment:{task_id}`:

- si la tarea está asignada a otro worker, publica progreso `rejected`
- registra fin `rejected`
- entra en modo de recuperación 30 segundos
- lanza `Reject(requeue=False)`

## Scheduler

`api/scheduler.py` ejecuta:

- descargas diarias
- descargas retroactivas
- limpieza de descargas
- altas
- matrículas
- consulta eNotum
- Data 360

## Consideraciones clave

- La cola de entrada real para negocio no es `robot_tasks`, sino `dispatcher_tasks_queue`.
- Redis es imprescindible incluso antes de llegar a Celery.
- El dispatcher aporta control operacional, pero también duplica parte del rol natural de Celery.
