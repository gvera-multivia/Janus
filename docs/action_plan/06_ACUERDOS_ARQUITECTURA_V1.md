# 06 – Acuerdos Finales de Arquitectura V1 (Contrato Dispatcher-Worker)

Este documento centraliza las 6 decisiones críticas de diseño acordadas antes de pasar a la fase de implementación (Execution Plane). Sirve como fuente de verdad para evitar ambigüedades durante el desarrollo de la V1.

---

### 1. Modelo de Cola (Redis)
**Decisión**: Push Dirigido + `BRPOP` Exclusivo.
- El Dispatcher decide la asignación y hace el routing **antes** de encolar.
- El Worker **no hace pull de un pool genérico**; simplemente escucha pasivamente y en exclusiva su clave `worker_queue:{worker_id}` mediante `BRPOP`.

### 2. Escritura Directa a SQL
**Decisión**: El Worker se conecta directamente a PostgreSQL (`psycopg`/`SQLAlchemy`).
- **Esquema Estable**: Las columnas centrales están garantizadas para V1.
- **Campos a actualizar por el worker**:
  - `status`: `RUNNING`, `COMPLETED`, `FAILED`, `COMPLETED_WITH_ERRORS`.
  - `started_at`: Al pasar a `RUNNING`.
  - `updated_at`: En cada cambio de estado final.
  - `result`: JSON con el *summary* final generado por el worker.
  - `error_message`: En caso de fallo técnico, traza del error.

### 3. Orden Exacto de Ejecución
**Decisión**: Para garantizar consistencia entre el estado SQL y los artefactos de disco, el Worker operará en este estricto orden:
1. Recibe la task desde Redis.
2. Valida la integridad del Payload.
3. Actualiza el estado en PostgreSQL a `RUNNING` + `started_at = NOW()`.
4. Persiste el recibo en disco: `input.json`.
5. Ejecuta la lógica de automatización cliente a cliente.
6. Persiste evidencias en disco: `results.json` y `summary.json`.
7. Actualiza PostgreSQL con estado final (`COMPLETED` o `FAILED`), volcando el summary interno a la base de datos.

### 4. Timeouts y Recuperación de Jobs
**Decisión**: Gestión Manual para la V1.
- **Worker Muerto:** Si el heartbeat de Redis (`worker_status:{id}`) caduca (ej. 30s), el Dispatcher asume que está offline y no le mandará más trabajo.
- **Job Huérfano:** Si un worker muere estando en `RUNNING`, el job quedará colgado. En la V1, **no habrá reencolado automático**. El Dispatcher emitirá alertas y un operador o un script de recuperación podrá relanzarlos cambiando su estado a `PENDING`. (Relanzar automáticamente automatizaciones de navegador es peligroso sin verificar si se dejó una sesión abierta).

### 5. Idempotencia y Doble Ejecución
**Decisión**: Validación Estricta.
- El Worker, al recibir una tarea (paso 2), verificará que el estado en DB sigue siendo `ASSIGNED` u homologable.
- Si el `task_id` ya consta como `RUNNING` (por otro worker) o `COMPLETED` en la base de datos, el Worker la descartará silenciosamente.
- **Única fuente de reencolado**: Solo el Dispatcher o un administrador explícito puede reencolar alterando el flag SQL, nunca un componente o cola duplicada.

### 6. Payload Final V1
**Decisión**: Estructura de Transporte Inmutable para el desarrollo.

```json
{
  "task_id": "uuid-1234",
  "job_id": "uuid-1234",
  "worker_id": "worker-01P",
  "task_name": "run_sede_job",
  "sede": "dehu",
  "source": "dispatcher",
  "metadata": {},
  "clientes": [
    {
       "nif": "123",
       "nombre": "Acme",
       "email": "a@a.com",
       "id_redtrust": "RT-01"
    }
  ]
}
```
*Aclaración: Añadir el `worker_id` al payload permite al worker un doble check rápido de que realmente el mensaje era para él sin consultar DB.*
