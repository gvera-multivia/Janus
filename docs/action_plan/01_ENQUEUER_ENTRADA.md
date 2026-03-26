# 01 – Enqueuer: Punto de Entrada al Dispatcher

## Contexto

El Enqueuer (`api/enqueuer.py`) es la puerta de entrada al sistema de distribución. Su única responsabilidad es validar que una tarea es legítima y colocarla en la cola Redis `dispatcher_tasks_queue`. Desde ahí, el Dispatcher la consumirá.

---

## Código fuente

**Archivo principal**: `api/enqueuer.py` (72 líneas)

---

## Tareas

### Función `enqueue_task()`

- [ ] Revisar la firma de `enqueue_task(task_name, args=None, kwargs=None)` en `api/enqueuer.py:11`:
  - **Input**: nombre del robot, argumentos posicionales (list), argumentos con nombre (dict)
  - **Output**: dict con `status` ('success'/'error'), `message`, y `task_data` (si éxito)
  - **Acción interna**: hace `RPUSH` del JSON serializado a `dispatcher_tasks_queue` en Redis.
  - **Query Redis**: `RPUSH dispatcher_tasks_queue '{"task": "...", "args": [...], ...}'`

- [ ] Verificar la validación contra `get_robot_tasks()` (línea 39):
  - Se importa desde `api/routes/status.py`: `from api.routes.status import get_robot_tasks`
  - Si `task_name` no está en la lista de tareas válidas → retorna error sin encolar
  - **Dependencia**: `api/routes/status.py` define qué robots existen

- [ ] Verificar el formato del JSON que se encola (líneas 50-56):
  ```json
  {
    "task": "run_robot_descargas",
    "args": [],
    "kwargs": {},
    "timestamp": 1710000000.0,
    "enqueued_by": "api"
  }
  ```
  - **Problema detectado**: no se genera `task_id` aquí. El campo NO se incluye en el JSON encolado
  - El `task_id` se genera después en el Dispatcher (`dispatch_task_to_worker()` línea 167)

### BUG: Ausencia de `task_id` en el encolado

- [ ] **BUG – El `task_id` nace demasiado tarde**: El JSON que entra a `dispatcher_tasks_queue` NO tiene `task_id`:
  - **Consecuencia 1**: no se puede deduplicar tareas en la cola de entrada
  - **Consecuencia 2**: si la tarea se reencola (worker no disponible), al retomarla puede generar un nuevo `task_id`
  - **Consecuencia 3**: no hay identidad de negocio persistente desde el momento del encolado
  - **Corrección propuesta**: generar `task_id = str(uuid.uuid4())` en `enqueue_task()` e incluirlo en el JSON:
    ```python
    task_data = {
        'task': task_name,
        'task_id': str(uuid.uuid4()),  # AÑADIR ESTO
        'args': args or [],
        'kwargs': kwargs or {},
        'timestamp': time.time(),
        'enqueued_by': 'api'
    }
    ```
  - **Archivo**: `api/enqueuer.py` líneas 50-56

### BUG: Ausencia de deduplicación

- [ ] **BUG – No hay deduplicación en el encolado**:
  - Si se llama a `enqueue_task()` dos veces con los mismos parámetros, se encolan DOS tareas idénticas
  - No hay ningún check previo contra `dispatcher_tasks_queue` para evitar duplicados
  - **Corrección propuesta**: antes del `RPUSH`, verificar si ya existe una tarea con los mismos `task_name` + `kwargs` en la cola:
    ```python
    # Opción A: hash del payload como key de deduplicación en Redis con TTL
    dedup_key = f"dedup:{task_name}:{hash(json.dumps(kwargs, sort_keys=True))}"
    if not r.set(dedup_key, 1, nx=True, ex=60):
        return {'status': 'duplicate', 'message': 'Task already enqueued'}
    ```
  - **Archivo**: `api/enqueuer.py`

### Conexión Redis independiente

- [ ] Verificar que `enqueue_task()` crea su propia conexión Redis cada vez que se llama (líneas 47-48):
  ```python
  r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
  ```
  - No reutiliza una conexión pool
  - Cada llamada crea nueva conexión → overhead en escenarios de alta frecuencia
  - **Mejora propuesta**: usar un pool de conexiones Redis compartido o un singleton

### Variables de entorno necesarias

- [ ] Verificar que `.env` contiene las variables necesarias para el Enqueuer:
  - `REDIS_HOST`: host del servidor Redis
  - `REDIS_PORT`: puerto del servidor Redis
  - **Archivo de referencia**: `.env.example`

---

## Consultas SQL de Origen (Discovery)

Estas consultas son ejecutadas por el Scheduler o la API antes de llamar a `enqueue_task`.

### 1. Limpieza de Descargas (Dehú/eNotum/DEV)
**Ubicación**: `database/descargas/queries/getNotificacionesDehu.py`
**Lógica**: Busca notificaciones pendientes en los últimos N días para sedes específicas.
```sql
SELECT em.message_key
FROM [dbo].[emails_messages] em
INNER JOIN [dbo].[certificates_sedes_cat] cs ON em.sedes_cat_id = cs.id
INNER JOIN [dbo].[emails_status] es ON em.status_id = es.id
WHERE 
    em.customer_number IS NOT NULL
    AND em.parent_id IS NULL
    AND em.date >= GETDATE() - %s AND em.date < GETDATE()-1 -- %s = less_days
    AND LOWER(cs.sede) IN (%SEDES_PLACEHOLDER%)
    AND em.body_html IS NOT NULL
    AND es.name IN ('Pendiente')
    AND (em.UsuarioAsignado IS NULL OR em.UsuarioAsignado = 'Adría Martínez')
```

### 2. Generación de Tarea Data 360 (Matrículas)
**Ubicación**: `api/scheduler.py:160`
**Lógica**: Identifica clientes premium con servicio Data 360 priorizando los que llevan más tiempo sin procesar.
```sql
WITH ha_latest AS (
    SELECT ha.*, ROW_NUMBER() OVER (PARTITION BY ha.cliente ORDER BY ha.created_at DESC) AS rn
    FROM historico_automatizaciones ha 
    INNER JOIN informes_dgt_automatizaciones ida ON ida.execution_id = ha.execution_id
)
SELECT Distinct idbenef as cliente,
    CASE WHEN ha.robot_name = 'RobotInformesDGT' THEN ha.created_at ELSE NULL END as last_date
FROM info.BeneficiarioBonos ibb
LEFT JOIN ha_latest ha ON ha.cliente = ibb.idbenef AND ha.rn = 1
WHERE 1=1
    AND ibb.servicio IN ('DATA_360_TRAFICO', 'DATA_360_TRAFICO Económico')
    AND ibb.situacion LIKE '%COBRADO%'
ORDER BY last_date ASC
```

### 3. Descargas Pendientes Estándar
**Ubicación**: `database/descargas/queries/getNotificacionesPendientes.py`
**Lógica**: Query compleja (180+ líneas) que valida servicios activos, contratos vigentes y situación de cobro antes de permitir la descarga.
- **Filtro Crítico**: `situacion IN ('COBRADO','COBRADO (RECUPERADO)','PENDIENTE VT','ESPECIAL HP')`
- **Filtro Certificados**: `cm.result = 'Vigente' AND cm.state = 'Completado'`

### 4. Altas Pendientes Estándar
**Ubicación**: `database/altas/queries/getAltasPendientes.py`
**Lógica**: Busca clientes con certificados vigentes y sedes donde no tienen acción registrada aún.
```sql
SELECT cm.customer_number AS cliente, cs.certificate_id, cs.sede
FROM certificates_sedes cs 
INNER JOIN certificates_managements_ cm ON cm.id = cs.certificate_id
LEFT JOIN clientes c ON c.numerocliente = cm.customer_number
WHERE
    cs.sede IN ({sedes_placeholder})
    AND cs.action IS NULL AND (cs.state IS NULL or cs.state = 1)
    AND cm.result = 'Vigente' AND cm.state = 'Completado'
    AND cm.valid_from <= GETDATE() AND cm.valid_up_to >= GETDATE()
    AND NOT EXISTS (
        SELECT 1 FROM automations_assignment_log aal
        WHERE aal.id = 'alta_' + CAST(cm.customer_number AS VARCHAR(50)) + '_' + LOWER(cs.sede)
        AND aal.robot_name = 'RobotAltas'
    )
```
