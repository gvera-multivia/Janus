# Guía 05: Plan de Acción - Comunicación entre Dispatcher y Automatizaciones (Robots)

El objetivo de esta guía es definir de manera precisa cómo debe ser la comunicación y orquestación entre el componente **Dispatcher** y las **Automatizaciones** (como el robot de Dehú y futuros robots para otras sedes).

---

## 1. El Objetivo del Dispatcher

El **Dispatcher** es un orquestador agnóstico y centralizado cuyo único objetivo es **distribuir trabajo de forma inteligente y segura** a una flota de workers (robots), sin conocer los detalles de negocio de lo que está ejecutando.

Las responsabilidades exclusivas del Dispatcher son:
- **Descubrimiento y monitoreo:** Saber qué workers están activos y evaluar su carga (CPU, RAM, tareas recientes) a través de un sistema de heartbeats en Redis.
- **Enrutamiento (Scoring):** Elegir el worker más adecuado y libre para ejecutar una tarea.
- **Reserva atómica:** Evitar la duplicidad de ejecuciones asegurando en Redis que una tarea solo se asigne a un único worker.
- **Despacho:** Enviar la tarea al worker seleccionado utilizando un sistema de colas (Celery/Redis).

El Dispatcher **NO debe**:
- Leer, entender ni validar el contenido del payload (ej. NIFs, URLs, nombres de sedes).
- Tener hardcodeadas lógicas de negocio, tipos de robot o URLs de sedes (como `dehu`, `enotum`, etc.).
- Conectarse directamente a las páginas web de destino.

---

## 2. El Principio de Modularidad en las Automatizaciones

Como se observa en el robot de ejemplo (`dehu_automation`), actualmente el robot se puede ejecutar leyendo de un archivo estático local (`clientes.json`). En el entorno productivo, el robot pasará a ser un "worker" que escucha órdenes enviadas por el Dispatcher.

**El requerimiento clave de la arquitectura es la modularidad y la escalabilidad multi-sede.**

Dehú es solo **una** de las muchas automatizaciones que existirán. Habrá robots para eNotum, DGT, sedes judiciales, etc. Para que todo fluya de forma genérica:

1. **El Payload es Agnóstico:** El Dispatcher recibe un paquete opaco (`kwargs`) desde el "cerebro" (el enqueuer o base de datos) y simplemente lo transporta hasta el worker.
2. **Identificación por Metadata:** La información sobre *qué* automatización ejecutar y *dónde* (la "sede") debe viajar dentro del payload de la tarea, permitiendo que el worker que lo reciba inicialice dinámicamente el procesador adecuado.
3. **Desacoplamiento Total:** El código del Dispatcher no necesita modificarse cuando se añada una nueva sede o un nuevo robot; simplemente fluirán nuevos tipos de tareas (`task_name`) y nuevos payloads por la tubería de Redis/Celery.

---

## 3. Protocolo de Comunicación (Flujo de Orquestación)

La comunicación se rige por un flujo de transporte basado en mensajes JSON y reservas de estado en Redis:

### Fase A: Encolado de la Tarea (Enqueuer)
El sistema generador (scheduler o API) agrupa los clientes pendientes y encola un mensaje genérico en la lista de Redis `dispatcher_tasks_queue`.

**Ejemplo de Payload Genérico:**
```json
{
  "task": "run_generic_robot",
  "task_id": "8b51d450-410d-4050-b0db-b3b3a3734a2e",
  "args": [],
  "kwargs": {
    "job_id": "job_prod_20231010_1",
    "sede": "dehu",
    "clientes": [
      { "nif": "12345678Z", "nombre": "Empresa A", "email": "a@empresa.com", "id_redtrust": "RT-01" },
      { "nif": "87654321X", "nombre": "Empresa B", "email": "b@empresa.com", "id_redtrust": "RT-02" }
    ]
  },
  "timestamp": 1710000000.0,
  "enqueued_by": "scheduler"
}
```
*Nota: El campo `sede` viaja como parámetro dinámico, evitando cualquier hardcodeo en el Dispatcher.*

### Fase B: El Despacho (Dispatcher)
1. El Dispatcher lee el JSON de `dispatcher_tasks_queue`.
2. Filtra a los workers disponibles y selecciona el que tenga mejor "score" (menos CPU/RAM).
3. Escribe en Redis una reserva atómica (`SET task_assignment:{task_id} {worker_id} NX EX 14400`).
4. Utiliza Celery para enviar el comando de ejecución a la cola `robot_tasks`. El Dispatcher envía el `task_name` (`run_generic_robot`) y el payload opaco `kwargs`.

### Fase C: Ejecución en el Worker (Automatización)
El robot (que está ejecutándose como un worker de Celery) recibe la tarea.

Su proceso de adaptación desde el modo "local" (`clientes.json`) al modo "worker" es el siguiente:
1. **Validación de Identidad:** El worker lee su propia IP/hostname y verifica en Redis (`task_assignment:{task_id}`) si realmente él es el propietario de esa tarea.
2. **Arranque Dinámico (Factoría):** El worker lee la variable `sede` del payload y, utilizando un patrón de factoría (ej. `get_site_processor(sede)` que ya existe en `dehu_automation`), inicializa la automatización específica para Dehú, eNotum, etc.
3. **Ejecución y Progreso:** Mientras procesa el listado de clientes, el worker publica el porcentaje de progreso de vuelta a Redis (`task_progress:{task_id}`).
4. **Finalización:** Al terminar, el worker registra el fin en la clave `task_registry:{worker_id}` de Redis, borra su progreso en tiempo real y guarda el resumen (Altas, Errores, etc.) en la base de datos SQL.

---

## 4. Resumen de Adaptación para Robots

Para que cualquier script de automatización (como `dehu_automation/main.py`) se integre a este sistema modular, debe cumplir estos puntos:

- [ ] **No depender de archivos locales:** En producción, no usar `sys.argv` o `clientes.json`. La función principal debe recibir un diccionario de `kwargs` proporcionado por Celery.
- [ ] **Ser agnóstico de la sede:** Delegar la creación del driver/procesador web a un `Registry` o `Factory` que lea la `sede` del payload y devuelva la clase correspondiente.
- [ ] **Comunicación con Redis:** Importar y usar `api.redis.RedisManager` para notificar:
  - `register_task_start()`: al iniciar.
  - `publish_task_progress()`: tras procesar cada cliente.
  - `register_task_end()`: al finalizar, reportando el número de éxitos y errores.

---

## [NUEVO] Propuesta Estratégica: Protocolo Custom Workers (Sin Celery)

Para hacer el sistema más predecible y aislar verdaderamente las cargas de trabajo, la arquitectura evolucionará eliminando Celery del proceso de despacho.

### 1. El Nuevo Flujo de Orquestación

#### Fase A: Encolado (Enqueuer)
El sistema genera un `task_id` (UUID) inmediato, lo registra en **PostgreSQL** (`execution_history`) como `PENDING` para garantizar auditoría, y luego inserta el JSON genérico en `dispatcher_tasks_queue` de Redis.

#### Fase B: El Despacho (Dispatcher)
1.  El Dispatcher saca la tarea de `dispatcher_tasks_queue`.
2.  Busca el mejor worker disponible (usando heartbeats de Redis + carga histórica de PostgreSQL).
3.  Actualiza el estado en PostgreSQL a `ASSIGNED`.
4.  **Inyecta la tarea directamente en la cola privada del worker en Redis** (`LPUSH worker_queue:{worker_id}`).

#### Fase C: Ejecución en el Worker (Robot como Proceso Puro)
El robot ya no necesitará el framework de Celery. Será un script/demonio de Python puro que:
1.  **Bloqueo de Escucha:** Hará `BRPOP worker_queue:{worker_id}` para esperar tareas sin consumir CPU.
2.  **Confirmación de Inicio:** Al recibir la tarea, actualizará inmediatamente su estado en PostgreSQL a `RUNNING`.
3.  **Ejecución de Negocio:** Instanciará el procesador correspondiente (ej. Dehú) pasando los `kwargs`.
4.  **Finalización Fuerte:** Actualizará PostgreSQL a `COMPLETED` o `FAILED` con el resultado json estructurado.

### 2. Nuevos Requisitos de Adaptación para Robots

Para que un script existente pase a funcionar bajo este modelo de "Custom Worker":

-   [ ] **Clase Base Unificada**: Deben heredar o instanciar una `BaseWorker` que se encargue automáticamente del hilo secundario de heartbeats (actualizando `worker_status:{id}` cada 10s en Redis).
-   [ ] **Sustitución de Celery API**: Eliminar atributos como `self.request.id`. El `task_id` vendrá explícitamente en el payload JSON.
-   [ ] **Cliente PostgreSQL Directo**: Reemplazar las llamadas asíncronas de registro de estado en Redis (`task_registry`) por inserts estructurados usando `psycopg` o SQLAlchemy hacia la tabla central `execution_history`.

---

## [NUEVO] Contrato Dispatcher <-> Worker (Alineación)

Base operativa establecida en `dispatcher_worker_integration_contract.md`.

### Payload Estándar de Entrada

El Dispatcher inyectará a la cola del worker (`worker_queue:{id}`) un JSON estandarizado que el worker (Adapter) debe aceptar obligatoriamente:

```json
{
  "task_name": "run_sede_job",
  "task_id": "UUID-1234",
  "job_id": "UUID-1234",
  "worker_id": "worker-01P",
  "sede": "dehu",
  "source": "dispatcher",
  "clientes": [
    {
      "nif": "12345678A",
      "nombre": "Empresa S.L",
      "email": "contacto@empresa.com",
      "id_redtrust": "43534 -"
    }
  ]
}
```
*El worker (Adapter) traducirá esto internamente, pero de cara al Dispatcher, este es el contrato inmutable en v1.*

### Orden Estricto de Ejecución

Para garantizar la consistencia entre PostgreSQL y el almacenamiento local, el Worker debe seguir este orden exacto:
1. Recibe la task desde Redis.
2. Valida la integridad del Payload.
3. Actualiza el estado en PostgreSQL a `RUNNING` (guardando `started_at`).
4. Persiste de inmediato en disco: `input.json`.
5. Ejecuta la automatización (job).
6. Persiste las evidencias en disco: `results.json` y `summary.json`.
7. Actualiza PostgreSQL con estado final (`COMPLETED`, `COMPLETED_WITH_ERRORS` o `FAILED`).

### Artefactos de Salida Esperados

El Dispatcher no extraerá el detalle de negocio de Redis ni PostgreSQL. El Worker debe seguir su ciclo estándar de escritura en su almacenamiento/red local, generando estrictamente:

Ruta base por ejecución: `outputs/jobs/<job_id>/`

1.  `input.json`: Snapshot exacto del input recibido.
2.  `results.json`: Detalle (cliente a cliente) de éxito/fallo (`duracion`, `fase_error`, `captura_error`, etc).
3.  `summary.json`: El archivo **canónico** para sistemas externos. Deberá reflejar el estado global y agregaciones (`exitos`, `errores`, `duracion_total`).

El Dispatcher asumirá que el lifecycle del task finaliza una vez recibe la señal final en PostgreSQL, asumiendo que estos artefactos ya residen en la carpeta pactada.
