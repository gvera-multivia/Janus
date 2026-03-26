# 03 – Redis: Estado Runtime del Dispatcher

## Contexto

Redis es el bus de control del Dispatcher. Almacena la cola de entrada, los heartbeats de workers, las reservas de asignación, el progreso de tareas y el registro de actividad. El módulo `api/redis.py` (clase `RedisManager`, 199 líneas) centraliza las operaciones de estado. El Dispatcher accede a Redis directamente y también mediante `RedisManager` desde los workers.

---

## Código fuente

**Archivo principal**: `api/redis.py` (199 líneas)

**Métodos clave**:
| Método | Línea | Función |
|--------|-------|---------|
| `register_task_start()` | 41 | Marca inicio de tarea en registry |
| `publish_task_progress()` | 82 | Actualiza progreso en Redis |
| `register_task_end()` | 126 | Cierra tarea en registry |
| `assign_task()` | 177 | Reserva atómica (SET NX) |
| `get_task_assignment()` | 187 | Consulta asignación |
| `clear_task_assignment()` | 194 | Borra asignación |

---

## Tareas

### Claves Redis del Dispatcher

- [ ] Verificar la clave `dispatcher_tasks_queue`:
  - **Tipo**: Lista Redis
  - **Operaciones**: `RPUSH` (enqueuer), `LPOP` (dispatcher), `RPUSH` (requeue por dispatcher)
  - **Sin TTL**: persistente mientras Redis esté activo
  - **Escritura**: `api/enqueuer.py` línea 58, `api/dispatcher.py` líneas 357/363/375
  - **Lectura**: `api/dispatcher.py` línea 322

- [ ] Verificar la clave `worker_status:{worker_id}`:
  - **Tipo**: String con JSON serializado
  - **Campos del JSON**: `ip`, `hostname`, `status` (Free/Busy), `cpu_percent`, `memory_percent`, `timestamp`, `current_task`, `pid`, `uptime`, `disk`, `network`
  - **TTL**: 30 segundos (se renueva cada 10s por el heartbeat del worker)
  - **Escritura**: workers (en `api/worker.py`)
  - **Lectura**: `api/dispatcher.py` líneas 68-69 y 105-106

- [ ] Verificar la clave `task_assignment:{task_id}`:
  - **Tipo**: String con `worker_id` como valor
  - **Creación**: `SET key worker_id NX EX 14400`
  - **Borrado**: `register_task_end()` (línea 168 de redis.py)
  - **Counterpart SQL**: Al arrancar, el robot inserta en `automations_assignment_log` para persistencia duradera.
  - **Query SQL (Insert)**: `INSERT INTO automations_assignment_log (id, cliente, sede, robot_name, assigned_at, assigned_by) VALUES (%s, %s, %s, %s, GETDATE(), %s)`
  - **Query SQL (Delete)**: `DELETE FROM automations_assignment_log WHERE robot_name = %s AND id = %s`
  - **Ubicación**: `database/database_manager.py:285`

- [ ] Verificar la clave `task_registry:{worker_id}`:
  - **Tipo**: Hash Redis que almacena el estado operacional vivo de cada tarea.
  - **Counterpart SQL**: Al finalizar, el robot persiste el resultado en `historico_automatizaciones`.
  - **Query SQL (Insert)**:
    ```sql
    INSERT INTO historico_automatizaciones (
        execution_id, cliente, nif, cif, tipo_cliente, 
        robot_name, status, sede, result_robot, 
        result_certificate, execution_message, 
        updated_by_user_id, updated_by_user_name, created_at
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, GETDATE())
    ```
  - **Query SQL (Update)**:
    ```sql
    UPDATE historico_automatizaciones 
    SET status = %s, result_robot = %s, result_certificate = %s, 
        execution_message = %s, updated_at = GETDATE()
    WHERE execution_id = %s
    ```
  - **Ubicación**: `database/database_manager.py:130, 167`

- [ ] Verificar la clave `task_progress:{task_id}`:
  - **Tipo**: String con JSON serializado
  - **TTL**: 600 segundos (10 minutos) → `setex()` en línea 109
  - **Escritura**: `publish_task_progress()` línea 109
  - **Borrado**: `register_task_end()` línea 163

- [ ] Verificar la clave `task_assignment_log`:
  - **Tipo**: Lista Redis
  - **Contenido**: JSON con: `task_id`, `task_name`, `worker_id`, `worker_ip`, `args`, `kwargs`, `timestamp`, `assigned_by`
  - **Escritura**: `dispatcher.py` línea 269
  - **Truncado**: a 1000 entradas en `cleanup_expired_data()` línea 297

- [ ] Verificar la clave `celery-task-meta-{task_id}`:
  - **Tipo**: String (metadatos nativos de Celery)
  - **Borrado**: en `register_task_end()` línea 164

---

### RedisManager: `register_task_start()` (línea 41)

- [ ] Verificar la estructura del JSON que se escribe en `task_registry:{worker_id}`:
  ```json
  {
    "task_id": "...",
    "task_name": "run_robot_descargas",
    "worker_id": "192.168.1.100@HOSTNAME",
    "worker_ip": "192.168.1.100",
    "pid": 12345,
    "status": "running",
    "args": [],
    "kwargs": {},
    "start_time": "2026-03-25T14:00:00",
    "created_at": "2026-03-25T14:00:00",
    "updated_at": "2026-03-25T14:00:00",
    "end_time": null,
    "progress": 0,
    "final_result": null,
    "error": null
  }
  ```
  - Si `worker_id` no se pasa, se construye como `{ip}@{hostname}` (líneas 54-56)

---

### RedisManager: `publish_task_progress()` (línea 82)

- [ ] Verificar el doble write en progreso (líneas 109-121):
  - **Write 1**: `task_progress:{task_id}` con TTL 600s (progreso vivo, short-term)
  - **Write 2**: actualiza `task_registry:{worker_id}` → solo `status` y `updated_at`
  - Esto permite que el estado live tenga más detalle que el registry

---

### RedisManager: `register_task_end()` (línea 126)

- [ ] Verificar la firma: `register_task_end(task_id, worker_id=None, status='completed', error=None)`
  - `worker_id` es el SEGUNDO parámetro posicional (con default None)
  - `status` es el TERCER parámetro con default `'completed'`

- [ ] **BUG CRÍTICO – Llamadas incorrectas desde `api/worker.py`**:
  - **Llamada actual (éxito)**: `register_task_end(task_id, 'completed')` → `worker_id='completed'`, `status='completed'` (default)
  - **Llamada actual (error)**: `register_task_end(task_id, 'failed', str(e))` → `worker_id='failed'`, `status=str(e)`
  - **Consecuencia**: se crean/actualizan hashes bajo `task_registry:completed` y `task_registry:failed` en vez del worker real
  - **Efecto visible**: estado zombi, tareas que parecen activas pero ya terminaron
  - **Corrección propuesta**:
    ```python
    # ÉXITO:
    register_task_end(task_id, worker_id=actual_worker_id, status='completed')
    # ERROR:
    register_task_end(task_id, worker_id=actual_worker_id, status='failed', error=str(e))
    ```
  - **Archivo a corregir**: `api/worker.py` (todas las llamadas a `register_task_end`)

- [ ] Verificar la limpieza que hace `register_task_end()`:
  - Actualiza `task_registry:{worker_id}` con `end_time`, `status`, `error` (línea 159)
  - Borra `task_progress:{task_id}` (línea 163)
  - Borra `celery-task-meta-{task_id}` (línea 164)
  - Borra `task_assignment:{task_id}` via `clear_task_assignment()` (línea 168)
  - Un `print()` de debug dejado en producción (línea 145, 162) → limpiar

---

### RedisManager: Métodos de asignación

- [ ] Verificar `assign_task()` (línea 177):
  - Usa `redis.set(key, worker_id, nx=True, ex=expire)` → reserva atómica
  - Retorna `True` si se reservó, `False` si ya existía
  - **Nota**: el Dispatcher NO usa este método; hace `self.redis_client.set()` directamente en `dispatch_task_to_worker()` (línea 206)
  - **Mejora propuesta**: que el Dispatcher use `RedisManager.assign_task()` para centralizar la lógica

- [ ] Verificar `get_task_assignment()` (línea 187):
  - Lee `task_assignment:{task_id}` y devuelve el `worker_id` asignado
  - Usado por los workers para verificar si la tarea les corresponde

- [ ] Verificar `clear_task_assignment()` (línea 194):
  - Borra `task_assignment:{task_id}`
  - Usado en `register_task_end()` y en el bucle de polling del Dispatcher

---

### Variables de entorno de RedisManager

- [ ] Verificar las variables en `api/redis.py` (líneas 15-22):
  | Variable | Default | Usada en |
  |----------|---------|----------|
  | `REDIS_HOST` | *(obligatoria)* | Conexión |
  | `REDIS_PORT` | *(obligatoria)* | Conexión |
  | `WORKER_STATUS_KEY` | `worker_status` | Heartbeats |
  | `TASK_PROGRESS_KEY` | `task_progress` | Progreso live |
  | `TASK_REGISTRY_KEY` | `task_registry` | Registro de tareas |
  | `TASK_ASSIGNMENT_KEY` | `task_assignment` | Reservas |
  | `TASK_ASSIGNMENT_EXPIRE` | `14400` | TTL reserva |

---

### Limpieza completa de Redis (reset operativo)

- [ ] Para un reset total del sistema de dispatcher:
  ```powershell
  redis-cli -n 0 FLUSHDB
  ```
  Esto elimina: colas, heartbeats, progreso, assignments, logs, bindings Celery

- [ ] Para limpieza selectiva (solo dispatcher, sin afectar Celery):
  ```bash
  redis-cli DEL dispatcher_tasks_queue
  redis-cli DEL task_assignment_log
  redis-cli --scan --pattern "worker_status:*" | xargs redis-cli DEL
  redis-cli --scan --pattern "task_registry:*" | xargs redis-cli DEL
  redis-cli --scan --pattern "task_progress:*" | xargs redis-cli DEL
  redis-cli --scan --pattern "task_assignment:*" | xargs redis-cli DEL
  ```

- [ ] Limpiar también claves Celery si se quiere reset completo:
  ```bash
  redis-cli --scan --pattern "celery-task-meta-*" | xargs redis-cli DEL
  redis-cli DEL unacked
  redis-cli DEL unacked_index
  redis-cli DEL robot_tasks
  ```
