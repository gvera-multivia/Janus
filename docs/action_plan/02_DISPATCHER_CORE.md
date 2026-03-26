# 02 – Dispatcher: Motor de Decisión y Distribución

## Contexto

El Dispatcher (`api/dispatcher.py`, clase `Dispatcher`, 418 líneas) es el cerebro del sistema de distribución. Corre en un bucle infinito que: (1) consume tareas de `dispatcher_tasks_queue`, (2) descubre workers vivos por heartbeat Redis + Celery Inspect, (3) filtra workers con estado `Free`, (4) aplica scoring para elegir el mejor, (5) reserva la asignación atómicamente en Redis, y (6) envía la tarea vía `celery.send_task()`.

---

## Código fuente

**Archivo principal**: `api/dispatcher.py` (418 líneas)

**Métodos clave**:
| Método | Línea | Función |
|--------|-------|---------|
| `__init__` | 29 | Inicializa Redis, logger, config |
| `get_alive_workers()` | 51 | Descubre workers vivos |
| `get_available_workers()` | 97 | Filtra workers con estado `Free` |
| `select_best_worker()` | 118 | Algoritmo de scoring |
| `dispatch_task_to_worker()` | 159 | Reserva + envío + polling |
| `cleanup_expired_data()` | 281 | Limpieza periódica |
| `dispatch_tasks()` | 304 | Bucle principal |
| `get_dispatcher_status()` | 393 | Estado del dispatcher |

---

## Tareas

### Inicialización (`__init__`, línea 29)

- [ ] Verificar las variables de entorno que lee la clase `Dispatcher`:
  - `REDIS_HOST` / `REDIS_PORT` → URL de conexión
  - `WORKER_STATUS_KEY` → prefijo de heartbeats (default: `"worker_status"`)
  - `TASK_PROGRESS_KEY` → prefijo de progreso (default: `"task_progress"`)
  - `TASK_ASSIGNMENT_KEY` → prefijo de asignaciones (default: `"task_assignment"`)
  - `TASK_ASSIGNMENT_EXPIRE` → TTL de la reserva en segundos (default: `14400` = 4 horas)
  - **Archivo**: `api/dispatcher.py` líneas 21-27

- [ ] Verificar que `self.worker_timeout = 30` (línea 48):
  - Un worker cuyo heartbeat tenga más de 30 segundos se considera muerto
  - Este valor NO es configurable por variable de entorno (está hardcodeado)
  - **Mejora propuesta**: extraer a variable de entorno `WORKER_TIMEOUT`

- [ ] Verificar que `self.task_assignment_history = {}` (línea 49):
  - Diccionario en memoria (NO persistido en Redis) que cuenta tareas asignadas por worker
  - Se usa para el factor de "carga reciente" en el scoring
  - **Riesgo**: si el dispatcher se reinicia, se pierde el historial y el balanceo resetea

---

### Descubrimiento de workers (`get_alive_workers()`, línea 51)

- [ ] Analizar el flujo de descubrimiento (líneas 51-95):
  1. Crea una instancia temporal de Celery: `Celery('robot_system', broker=REDIS_URL, backend=REDIS_URL)` (línea 57-61)
  2. Usa `Inspect(app=celery_app).active()` para obtener workers activos de Celery (línea 63-64)
  3. Para cada worker, lee el heartbeat en `worker_status:{worker_id}` de Redis (línea 68-69)
  4. Parsea el JSON, extrae `timestamp`, verifica que la diferencia con `now()` sea ≤ 30s (línea 73-75)
  5. Si está vivo, lo añade a la lista con sus métricas
  - **Output**: lista de dicts con `worker_id`, `ip`, `status`, `cpu_percent`, `memory_percent`, `tasks`

- [ ] **Problema: creación de instancia Celery en cada llamada** (línea 57-61):
  - Se crea un nuevo `Celery('robot_system', ...)` cada vez que se llama a `get_alive_workers()`
  - Este método se llama en cada iteración del bucle principal
  - **Impacto**: overhead de conexión y posible leak de conexiones
  - **Corrección propuesta**: mover la creación de la instancia Celery al `__init__` y reutilizarla

- [ ] Verificar manejo de errores por worker individual (línea 86):
  - Si un worker tiene heartbeat malformado (JSON inválido, campo faltante), se ignora sin crashear el dispatcher
  - Se loguea el error pero se continúa con el siguiente worker

---

### Filtrado de workers disponibles (`get_available_workers()`, línea 97)

- [ ] Analizar la lógica de filtrado (líneas 97-116):
  1. Obtiene workers vivos de `get_alive_workers()`
  2. Filtra solo los que tienen `status == 'Free'` (línea 103)
  3. Re-lee el heartbeat completo de Redis (segunda lectura, duplicada) para enriquecer datos (líneas 105-112)
  - **Problema**: doble lectura de `worker_status:{worker_id}` (una en `get_alive_workers` y otra aquí)
  - **Mejora propuesta**: pasar el `status_data` ya leído desde `get_alive_workers()` para evitar la segunda lectura

---

### Algoritmo de scoring (`select_best_worker()`, línea 118)

- [ ] Verificar la fórmula de scoring exacta (líneas 128-146):
  ```
  score = (100 - cpu_percent) * 0.4     // CPU libre: peso 40%
        + (100 - memory_percent) * 0.3   // RAM libre: peso 30%
        + max(0, 10 - recent_tasks) * 0.3 // Carga reciente: peso 30%
  ```
  - `cpu_percent` viene del heartbeat Redis; default 100 si falta el campo (línea 134)
  - `memory_percent` viene del heartbeat Redis; default 100 si falta el campo (línea 138)
  - `recent_tasks` viene de `self.task_assignment_history[worker_id]`; default 0 (línea 143)
  - **Score máximo teórico**: `100*0.4 + 100*0.3 + 10*0.3 = 40 + 30 + 3 = 73`
  - **Score mínimo teórico**: `0 + 0 + 0 = 0` (worker saturado + muchas tareas recientes)

- [ ] Verificar que la selección es por score descendente (línea 149):
  - `scored_workers.sort(key=lambda x: x[0], reverse=True)` → mayor score = mejor worker
  - En caso de empate, el orden depende de la estabilidad de Python sort (se mantiene orden original)

- [ ] Verificar que se actualiza el historial de asignaciones tras seleccionar (líneas 154-155):
  - `self.task_assignment_history[worker_id] += 1`
  - Este contador se resetea cada hora en `cleanup_expired_data()` (línea 290)
  - **Riesgo**: si se selecciona un worker pero luego falla el dispatch, el contador ya se incrementó

- [ ] **No hay afinidad por tipo de tarea**: El scoring no distingue entre tipos de robot
  - Todos los workers son iguales para todos los robots
  - **Mejora propuesta**: añadir "capacidades" por worker para filtrar antes del scoring

---

### Despacho de tarea (`dispatch_task_to_worker()`, línea 159)

- [ ] Analizar el flujo completo de despacho (líneas 159-279):
  1. Extrae `task_name`, `args`, `kwargs` del JSON
  2. Genera `task_id` si no viene en el JSON: `task_data.get('task_id') or str(uuid.uuid4())` (línea 167)
  3. Verifica que la tarea está registrada en Celery via `inspect.registered()` (líneas 177-196)
  4. **Entra en bucle de polling** (30s, polling cada 3s) (líneas 203-255)

- [ ] **BUG CRÍTICO – Reenvío de tareas dentro del bucle de polling** (líneas 203-255):
  - El `while elapsed < timeout` contiene DENTRO el `redis.set(NX)` + `celery.send_task()` (líneas 206-219)
  - En cada iteración del polling borra `task_assignment:{task_id}` en el `else` (línea 243) y reintenta
  - **Consecuencia**: la MISMA tarea se envía a Celery MÚLTIPLES VECES con el MISMO `task_id`
  - **Detalle línea por línea**:
    ```
    while elapsed < timeout:
        reserved = redis.set(assignment_key, worker_id, nx=True, ex=...)  # ← NX
        if not reserved: return False  # ← ya asignada, sale
        result = celery.send_task(...)  # ← ENVIA LA TAREA
        
        if result.state == 'STARTED': break        # ← OK, sale
        elif result.state in ('FAILURE','REVOKED'):
            redis.delete(assignment_key)            # ← borra reserva
        else:  # PENDING
            redis.delete(assignment_key)            # ← BORRA RESERVA
        
        sleep(3)
        elapsed += 3
        # ← VUELVE AL WHILE → RESERVA DE NUEVO → ENVIA DE NUEVO
    ```
  - **Resultado**: si el worker tarda >3s en pasar de PENDING a STARTED, el dispatcher:
    1. Borra la reserva
    2. Vuelve a reservar (NX tendrá éxito porque acaba de borrarla)
    3. Envía OTRA VEZ la misma tarea con el mismo `task_id`
  - **Corrección propuesta**: el `send_task()` y `set(NX)` deben ejecutarse UNA SOLA VEZ FUERA del bucle de polling. El bucle solo debe verificar `result.state`:
    ```python
    # Reservar una sola vez
    reserved = redis.set(assignment_key, worker_id, nx=True, ex=EXPIRE)
    if not reserved: return False
    
    # Enviar una sola vez
    result = celery.send_task(task_name, args, kwargs, queue='robot_tasks', task_id=task_id)
    
    # Polling: solo verificar estado
    while elapsed < timeout:
        if result.state == 'STARTED': break
        elif result.state in ('FAILURE', 'REVOKED'):
            redis.delete(assignment_key)
            return False
        sleep(poll_interval)
        elapsed += poll_interval
    ```
  - **Archivo**: `api/dispatcher.py` líneas 203-255

- [ ] **Problema secundario: instancia Celery creada en cada dispatch** (líneas 171-175):
  - Se crea `Celery('robot_system', ...)` otra vez dentro de `dispatch_task_to_worker()`
  - Son ya dos instancias por ciclo (una en `get_alive_workers`, otra aquí)
  - **Corrección propuesta**: usar una única instancia Celery en `self.celery_app` creada en `__init__`

- [ ] Verificar el manejo del `TimeoutError` (línea 255):
  - Si la tarea no pasa de PENDING en 30s → `raise TimeoutError`
  - Esto es capturado en `except (Exception, TimeoutError)` (línea 276) → retorna `False`
  - **Pero**: en el bucle principal (`dispatch_tasks`), tras `False` se reintenta hasta `max_retries=3` (líneas 341-348)
  - Esto puede generar hasta 4 envíos de la misma tarea × 10 polling loops = 40 mensajes duplicados

---

### Bucle principal (`dispatch_tasks()`, línea 304)

- [ ] Analizar el bucle principal completo (líneas 304-391):
  1. Lee longitud de cola `dispatcher_tasks_queue` (línea 312)
  2. `LPOP` de la cola (línea 322) → extrae tarea
  3. Si hay tarea:
     a. Obtiene workers disponibles (línea 331)
     b. Selecciona mejor worker (línea 335)
     c. Despacha (línea 339)
     d. Si falla: reintenta hasta 3 veces con sleep(2) (líneas 341-348)
     e. Si sigue fallando tras 3 reintentos: loguea error + sleep(5) (líneas 350-353)
  4. Si no hay workers: reinserta tarea en cola (`RPUSH`) + sleep(10) (líneas 360-364)
  5. Si no hay tareas: sleep(2) (líneas 377-379)
  6. Cada 5 minutos: `cleanup_expired_data()` (línea 382)

- [ ] **BUG – Tarea perdida tras max_retries**: Si el dispatch falla 3 veces (líneas 350-353):
  - Se loguea el error
  - Se hace `sleep(5)`
  - **Pero la tarea NO se reinserta en la cola** → se PIERDE silenciosamente
  - Solo se reinserta cuando: no hay workers disponibles (línea 363) o excepción general (línea 375)
  - **Corrección propuesta**: añadir `self.redis_client.rpush('dispatcher_tasks_queue', task_json)` tras agotar reintentos

- [ ] Verificar que la tarea se reinserta cuando no hay workers (líneas 357-364):
  - Si `select_best_worker` retorna `None` → `rpush` + sleep(5)
  - Si `get_available_workers` retorna `[]` → `rpush` + sleep(10)
  - ✅ Correcto: la tarea no se pierde en estos casos

- [ ] Verificar el mecanismo de `stop_event` (línea 309):
  - El bucle corre mientras `not stop_event.is_set()`
  - `stop_event` es un `threading.Event` pasado desde `api/server.py`
  - Al hacer `stop_event.set()`, el dispatcher para limpiamente tras la iteración actual

---

### Limpieza periódica (`cleanup_expired_data()`, línea 281)

- [ ] Verificar la lógica de limpieza (líneas 281-302):
  - Resetea `task_assignment_history` cada hora (líneas 289-293)
  - Recorta `task_assignment_log` a las últimas 1000 entradas (líneas 296-298)
  - **Se ejecuta cada ~5 minutos** desde el bucle principal (línea 382)
  - **Condición de ejecución**: `int(time.time()) % 300 == 0` → depende de que el segundo actual sea exactamente múltiplo de 300

- [ ] **Problema: condición de limpieza no fiable** (línea 382):
  - `int(time.time()) % 300 == 0` solo es `True` una vez por cada 300 segundos
  - Si el bucle no coincide exactamente en ese segundo → la limpieza no se ejecuta
  - **Corrección propuesta**: usar un timestamp de última limpieza:
    ```python
    if time.time() - self._last_cleanup_check > 300:
        self.cleanup_expired_data()
        self._last_cleanup_check = time.time()
    ```

---

### Estado del Dispatcher (`get_dispatcher_status()`, línea 393)

- [ ] Verificar el endpoint de status del dispatcher (líneas 393-417):
  - **Output**: dict con `running`, `queue_length`, `total_workers`, `available_workers`, `workers` (detalle), `task_assignment_history`, `timestamp`
  - Se usa desde algún endpoint API para monitorización
  - **Archivo**: `api/dispatcher.py`

---

### Variables de entorno del Dispatcher

- [ ] Crear/verificar todas las variables necesarias en `.env`:
  | Variable | Default | Descripción |
  |----------|---------|-------------|
  | `REDIS_HOST` | *(obligatoria)* | Host Redis |
  | `REDIS_PORT` | *(obligatoria)* | Puerto Redis |
  | `WORKER_STATUS_KEY` | `worker_status` | Prefijo claves heartbeat |
  | `TASK_PROGRESS_KEY` | `task_progress` | Prefijo claves progreso |
  | `TASK_ASSIGNMENT_KEY` | `task_assignment` | Prefijo claves asignación |
  | `TASK_ASSIGNMENT_EXPIRE` | `14400` | TTL reserva en seg (4h) |
  - **Archivo**: `.env.example`

---

## [NUEVO] Propuesta Estratégica: Migración a Custom Workers + PostgreSQL

Tras el análisis del Dispatcher y los problemas derivados de Celery, se ha propuesto y aprobado una nueva arquitectura que elimina Celery como dependencia y añade persistencia en PostgreSQL. 

**Esta sección documenta el objetivo final hacia el que evolucionarán las tareas anteriores.**

### Cambios Arquitectónicos Clave

1.  **Eliminación de Celery**: En lugar de usar `celery_app.send_task()`, el Dispatcher inyectará las tareas directamente en colas privadas de Redis específicas para cada worker (`worker_queue:{worker_id}`).
2.  **Historial en PostgreSQL**: El registro volátil en Redis (`task_assignment_history`) y las tablas de SQL Server (`automations_assignment_log`) se unificarán en una nueva tabla PostgreSQL `execution_history`.
3.  **Workers Ligeros**: Los robots dejarán de ser workers de Celery para convertirse en procesos Python estándar (`BaseWorker`) que escucharán su propia cola en Redis mediante `BRPOP`.

### Impacto en el Dispatcher (`api/dispatcher.py`)

- **Scoring Híbrido**: El algoritmo `select_best_worker` leerá métricas de CPU/RAM desde Redis, pero sumará la **carga histórica consultando PostgreSQL** (`COUNT(*) desde execution_history`).
- **Reserva Persistente**: La reserva atómica pasará de usar un simple flag `NX` en Redis a ser un registro con estado `ASSIGNED` en PostgreSQL.
- **Fin de los reenvíos duplicados (BUG CRÍTICO)**: El nuevo modelo elimina el bucle de polling que causaba envíos múltiples. El Dispatcher asigna (PostgreSQL) -> Encola (Redis) y pasa a la siguiente tarea.

### Beneficios Esperados
- Reducción drástica del consumo de CPU (sin overhead de Kombu ni procesos manager de Celery).
- Mayor capacidad de auditoría y análisis temporal gracias a PostgreSQL.
- Aislamiento real entre workers (cada uno tiene su cola privada).
