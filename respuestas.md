Basado en la arquitectura que hemos definido en los documentos [.md](cci:7://file:///c:/Users/Guillem%20Vera/Desktop/Proyectos/Janus/docs/legacy/00_INDEX.md:0:0-0:0) (específicamente en la `GUIA_05` y en el rediseño del `Dispatcher`), aquí tienes las respuestas exactas a las decisiones de diseño del contrato:

### 1. ¿Cómo me vas a enviar el trabajo?
**Respuesta:** Consumo desde Redis (Broker).
*   **Detalle:** El Dispatcher no llamará a una API tuya ni a un CLI. El Dispatcher inyectará la tarea en una lista de Redis exclusiva para ti llamada `worker_queue:{tu_worker_id}`.
*   **Tu responsabilidad:** Tu worker deberá estar ejecutando un proceso continuo con un `BRPOP` (bloqueo ligero) sobre esa cola esperando a que caigan los JSON.

### 2. Formato exacto del payload
**Respuesta:** Clientes completos (ya resueltos).
*   **Detalle:** El Dispatcher (o el Enqueuer antes que él) hará el trabajo pesado de base de datos. Recibirás un JSON autocontenido donde el array de `"clientes"` ya trae directamente el `nif`, `nombre`, `email` y el `id_redtrust`.
*   **Tu responsabilidad:** No tendrás que hacer queries adicionales para averiguar qué certificado usar o qué NIF pertenece a cada cliente; solo iterar sobre el array recibido y ejecutar la automatización.

### 3. ¿Cómo quieres que publique estado?
**Respuesta:** Modelo Híbrido (Redis para latido, SQL directo para el ciclo del Job).
*   **Heartbeat en Redis:** Para decir "estoy vivo, existo y mi nivel de CPU es X", tu worker actualizará direcamente la clave `worker_status:{tu_worker_id}` en Redis cada 10 segundos.
*   **Estado del Job en PostgreSQL:** Cuando cojas la tarea, cuando la acabes o si falla catastróficamente, harás un *UPDATE* directo (vía `psycopg`) a la tabla `execution_history` de PostgreSQL para cambiar el `status` a `RUNNING`, `COMPLETED` o `FAILED`.
*   *(Nota: Puedes abstraer esto en una clase base `BaseWorker` que haga esto por detrás para que el código de automatización quede limpio).*

### 4. ¿Cómo consumirás los resultados?
**Respuesta:** Esperaré la notificación SQL y (opcionalmente) leeré el `summary.json`.
*   **Detalle:** El Dispatcher sabrá que has terminado única y exclusivamente porque actualizaste el registro en PostgreSQL (`status = 'COMPLETED'`).
*   **Artefactos locales:** Yo no voy a parsear el detalle cliente a cliente. Yo confío en que, antes de lanzar la señal de fin a PostgreSQL, tú ya has guardado de manera local los archivos `input.json`, `results.json` y `summary.json` en tu ruta `outputs/jobs/<job_id>/`.
*   Si el sistema global o un dashboard posterior necesita ver un resumen, irá a buscar archivo `summary.json` que tú generaste en la carpeta compartida o volumen de red.