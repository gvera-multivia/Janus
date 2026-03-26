# Problemas Mayores, Procesos Fantasma y Reset Operativo

## Los problemas más grandes del proyecto

### 1. La orquestación está partida entre demasiadas capas

La ejecución real depende de:

- FastAPI
- `dispatcher_tasks_queue`
- dispatcher propio
- Celery
- Redis runtime
- SQL Server
- logs
- automatización GUI

Esto hace que no exista una única fuente de verdad. Cuando una tarea falla, se puede quedar viva o muerta en sitios distintos.

### 2. El dispatcher puede reenviar la misma tarea varias veces

En `api/dispatcher.py` el método `dispatch_task_to_worker` hace `send_task(...)` dentro de un bucle de polling. Si la tarea no pasa a `STARTED` enseguida:

- borra `task_assignment:{task_id}`
- vuelve a dormir
- vuelve a intentar enviar

Eso significa que una misma tarea puede publicarse varias veces en `robot_tasks` antes de que el primer worker llegue a marcarla como `STARTED`.

Consecuencia:

- duplicados
- rechazos
- workers entrando en recovery
- sensación de “procesos fantasma”

### 3. El `task_id` nace demasiado tarde

La cola de entrada `dispatcher_tasks_queue` no lleva `task_id` persistente desde el principio. El dispatcher genera uno al despachar.

Si la tarea se reencola o se reprocesa desde la cola de entrada:

- no hay identidad fuerte de negocio
- es más difícil deduplicar
- cada intento puede convertirse en una nueva ejecución lógica

### 4. `register_task_end` está mal llamado en los casos normales

En `api/worker.py` se invoca así en éxitos y fallos:

- `register_task_end(task_id, 'completed')`
- `register_task_end(task_id, 'failed', str(e))`

Pero la firma real en `api/redis.py` es:

```python
register_task_end(task_id, worker_id=None, status='completed', error=None)
```

Eso implica:

- `'completed'` se está usando como `worker_id`
- `'failed'` se está usando como `worker_id`
- el estado queda mal registrado
- se crean o actualizan hashes bajo claves erróneas

Este es uno de los mayores generadores de estado zombi o inconsistente.

### 5. Los endpoints de limpieza no limpian todo

`/api/system/clear-completed` y `/api/system/clear-running` solo borran entradas dentro de `task_registry:*`.

No limpian:

- `dispatcher_tasks_queue`
- `task_progress:*`
- `task_assignment:*`
- `celery-task-meta-*`
- `unacked`
- `unacked_index`
- la cola Celery `robot_tasks`

Por eso después de “limpiar” pueden seguir apareciendo tareas fantasma.

### 6. Dependencia extrema de GUI y ventanas

El sistema depende de:

- RedTrust en system tray
- títulos de ventana exactos
- foco de ventana
- tiempos y popups nativos

Eso introduce fallos imposibles de modelar bien solo con estado backend.

## Por qué se generan procesos fantasma o duplicados tras un ACK muy largo

La causa principal no es el `ack` largo por sí solo. La causa es la combinación de tres cosas:

### A. El dispatcher reenvía antes de tener confirmación estable

Mientras `result.state` siga en `PENDING`, el dispatcher interpreta que la tarea no ha arrancado todavía. Como el timeout interno es 30 segundos y reintenta cada 3:

- puede publicar la misma tarea varias veces
- puede soltar la reserva Redis antes de tiempo

### B. `visibility_timeout` es muy largo

En `api/worker.py`:

- `task_acks_late=False`
- `visibility_timeout=43200`

Ese `visibility_timeout` de 12 horas está pensado para tareas largas, pero combinado con mensajes duplicados y estados mal registrados hace que el sistema tarde mucho en “olvidar” restos de cola o mensajes no limpiados.

### C. El estado final se registra mal

Como `register_task_end` está mal llamado, el runtime puede quedar en un estado donde:

- la tarea terminó de verdad
- pero Redis no la cerró correctamente
- y Celery/Redis todavía muestran basura residual

### Resultado visible

- procesos Python/Celery aparentemente “sin hacer nada”
- tareas `running` o `pending` que ya no existen realmente
- workers entrando en recovery tras rechazos
- duplicación de robots después de una espera larga hasta `STARTED`

## Cómo quitar todos los elementos de las colas y reiniciar todo

## Opción 1. Limpieza lógica mínima desde la API

Sirve solo para quitar parte del runtime:

- `POST /api/system/clear-completed`
- `POST /api/system/clear-running`

Limitación:

- no vacía colas reales de Redis/Celery
- no mata workers
- no borra `task_progress:*`
- no borra asignaciones

## Opción 2. Reset operativo completo recomendado

### Paso 1. Parar entradas nuevas

Parar la API master o, como mínimo:

- deshabilitar llamadas entrantes
- parar el scheduler

Objetivo:

- que no entren nuevas tareas mientras limpias

### Paso 2. Parar todos los workers Celery

Hay que detener todos los procesos worker.

Si no, mientras limpias Redis pueden volver a escribir:

- heartbeat
- progreso
- estado de tarea

### Paso 3. Vaciar Redis de runtime y colas

Si quieres un reset total del DB `0` de Redis, la forma más limpia es:

```powershell
redis-cli -n 0 FLUSHDB
```

Eso elimina todo:

- colas del dispatcher
- colas Celery
- heartbeats
- progreso
- assignments
- resultados
- bindings y estados internos de Kombu/Celery

Si quieres limpieza selectiva en vez de `FLUSHDB`, debes borrar como mínimo:

- `dispatcher_tasks_queue`
- `task_assignment_log`
- `worker_status:*`
- `task_registry:*`
- `task_progress:*`
- `task_assignment:*`
- `celery-task-meta-*`
- `unacked`
- `unacked_index`
- `robot_tasks`

### Paso 4. Verificar que no queden procesos locales

Comprobar que no quedan:

- procesos `celery`
- procesos `python` de robots
- ventanas de navegador colgadas
- RedTrust bloqueado en una operación antigua

### Paso 5. Arrancar de nuevo en orden

Orden recomendado:

1. Redis
2. workers Celery
3. API master
4. scheduler

### Paso 6. Verificación post-reset

Comprobar:

- `GET /api/system/status`
- `GET /api/system/robot-tasks`
- que `dispatcher_tasks_queue` esté vacía
- que no existan `task_progress:*` antiguos
- que los workers publiquen `worker_status:*`

## Qué haría para arreglarlo de verdad

### Correcciones inmediatas

1. Corregir todas las llamadas a `register_task_end(...)` en `api/worker.py`.
2. Generar `task_id` en `enqueue_task`, no en el dispatcher.
3. Guardar ese `task_id` en `dispatcher_tasks_queue`.
4. Evitar que `dispatch_task_to_worker` haga `send_task(...)` varias veces para la misma tarea.
5. No borrar `task_assignment` mientras la tarea aún puede arrancar legítimamente.
6. Añadir un endpoint real de reset Redis/Celery o un script operativo explícito.

### Mejora estructural

Si el proyecto sigue creciendo, la simplificación correcta es:

- o usar Celery de forma más estándar y quitar el dispatcher propio
- o mantener dispatcher propio, pero sin reenviar por polling la misma tarea

Ahora mismo conviven ambos modelos y ese cruce es la fuente principal de inestabilidad.

## Por qué se piden altas pero no se están haciendo

Hay varias causas posibles en el código actual, y una de ellas es especialmente grave.

### Causa principal probable: se carga el certificado equivocado

En `app/robot_altas.py`, dentro de `subscribe_sedes(...)`, el código hace esto:

```python
if not self._load_certificate(str(client_id)):
```

Pero el certificado que realmente viene de base de datos está en:

- `alta["certificate_id"]`
- o `cert_tasks["certificate_id"]`

Es decir:

- `client_id` es el identificador del cliente
- `certificate_id` es el identificador del certificado

Si esos valores no coinciden, RedTrust intenta cargar un certificado que no existe o no corresponde al cliente. El efecto es:

1. falla `_load_certificate(...)`
2. se hace `continue`
3. no se entra en `_subscribe_sedes_with_certificate(...)`
4. no se ejecuta ninguna alta real

Eso encaja exactamente con el síntoma de “pedimos altas pero no se hacen”.

### Causa 2: hay filtros silenciosos que descartan sedes

En `_subscribe_sedes_with_certificate(...)` hay exclusiones por provincia:

- Barcelona/Girona/Lleida/Tarragona excluyen `baleares` y `mahon`
- `islas baleares` excluye `xaloc` y `oficina virtual ayuntamiento terrassa`
- el resto usa un `default_exclude`

Además, si `provincia` viene vacía:

```python
if not provincia:
    continue
```

Eso descarta la alta sin marcarla claramente como fallo operativo.

### Causa 3: una sede puede venir de BD pero no tener robot válido

El mapa `robot_class_map` en `app/robot_altas.py` es contrato duro. Si la sede:

- llega con otro nombre
- lleva distinta tilde
- viene con una variante no contemplada

entonces:

```python
robot_class = robot_class_map.get(sede)
if not robot_class:
    continue
```

La tarea queda sin ejecución real para esa sede.

### Causa 4: puede no haber altas elegibles en SQL aunque se haya lanzado la tarea

`AltasDatabase.fetch_altas(...)` filtra por:

- sedes
- cliente
- límite

Si la query no devuelve filas:

- la tarea sí arranca
- pero funcionalmente no hace nada

Desde fuera puede parecer que “el robot de altas no funciona”, cuando realmente no encontró pendientes compatibles.

### Causa 5: la asignación de certificado se hace antes de confirmar ejecución real

En `subscribe_sedes(...)`:

- se asignan certificados a usuario
- se insertan logs de asignación
- luego se intenta cargar certificado y ejecutar

Si la carga falla o la sede se salta por filtros:

- hay huella operativa de intención
- pero no hay alta efectiva

Eso genera sensación de inconsistencia.

### Causa 6: los resultados de proceso son heterogéneos y parte del flujo depende de ellos

Cada sede puede devolver:

- `check, action`
- o `check, action, email`

Si un robot devuelve algo distinto o falla sin llenar `result_queue`, el orquestador puede quedarse con:

- histórico insertado
- ninguna alta materializada
- mensaje ambiguo de “No results found”

## Diagnóstico concreto recomendado para altas

Cuando vuelva a pasar, comprobar en este orden:

1. si `fetch_altas(...)` devolvió filas
2. qué valor tiene `client_id`
3. qué valor tiene `certificate_id`
4. si `_load_certificate(...)` se está llamando con el `certificate_id` correcto
5. si la `provincia` está vacía o la sede cae en exclusión
6. si el nombre de sede coincide exactamente con `robot_class_map`
7. si `result_queue` recibe algún resultado real del robot

## Arreglo directo más importante para este síntoma

La corrección más probable es cambiar la carga de certificado en `RobotAltas` para usar `certificate_id` real y no `client_id`.

En otras palabras, esta parte:

```python
if not self._load_certificate(str(client_id)):
```

debería cargar algo equivalente a:

```python
if not self._load_certificate(str(cert_tasks.get("certificate_id"))):
```

o el campo correcto consolidado de certificado.
