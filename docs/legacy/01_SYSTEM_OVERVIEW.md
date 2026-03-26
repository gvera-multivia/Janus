# Visión General del Sistema

## Arquitectura real

El sistema sigue un patrón `master-worker`:

1. La API FastAPI recibe una petición o dispara una tarea programada.
2. `api/enqueuer.py` inserta la tarea en `dispatcher_tasks_queue` dentro de Redis.
3. `api/dispatcher.py` vigila esa cola, inspecciona workers vivos y decide asignación.
4. El dispatcher reserva la asignación en Redis y publica una tarea Celery en la cola `robot_tasks`.
5. Un worker Celery recibe la tarea, valida si realmente le fue asignada y, si procede, ejecuta el robot.
6. El robot consulta SQL Server, carga certificados, accede a portales externos, procesa resultados y actualiza histórico.
7. Redis conserva heartbeat, progreso y registro runtime de ejecución.

## Puntos de entrada

- API HTTP en `api/server.py`.
- Scheduler en `api/scheduler.py`.
- Workers Celery en `api/worker.py`.

## Capas del sistema

### Capa 1. Entrada y control

- FastAPI y rutas.
- Validación ligera de payload.
- Encolado de trabajo.

### Capa 2. Coordinación distribuida

- Dispatcher propio.
- Heartbeats de workers.
- Selección de worker por score simple.
- Scheduler temporal.

### Capa 3. Ejecución

- Tasks Celery registradas en `api/worker.py`.
- Rechazo de tareas asignadas a otro worker.
- Recuperación tras rechazo.

### Capa 4. Automatización

- Robots orquestadores.
- Robots portal-específicos.
- RedTrust.
- Selector nativo de certificado.

### Capa 5. Persistencia

- SQL Server con tablas operativas e histórico.
- Redis como estado runtime efímero.
- Ficheros de log por módulo.

## Módulos de negocio

- `app/robot_altas.py`
- `app/robot_descargas.py`
- `app/robot_consulta_enotum.py`
- `app/robot_matriculas_y_puntos.py`
- `app/robot_sede_judicial.py`

## Rasgos arquitectónicos importantes

- No existe un único origen de verdad de estado.
- El dispatcher no usa routing avanzado de Celery por worker; usa asignación lógica + verificación en el worker.
- Los robots usan `multiprocessing` para paralelizar fases de certificado y portal.
- Las tablas de assignment en SQL se usan para evitar colisiones funcionales.

## Riesgos estructurales

- Alta dependencia de UI automation y nombres de ventanas.
- Mezcla de colas propias y cola Celery.
- Posibles estados huérfanos entre Redis, Celery y SQL.
- Dependencia fuerte del naming exacto de sedes para mapear robots.
