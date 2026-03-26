# Lógica y Origen de los Datos (El "Por qué" y "Cómo")

Este documento explica con exactitud quién decide qué tareas se ejecutan, dónde reside esa lógica y cómo se extrae la información en el sistema RedTrust Automation.

---

## 1. ¿Quién decide qué se ejecuta? (El Motor)

El sistema tiene dos disparadores principales:

### A. El Scheduler (`api/scheduler.py`) - **Automático**
Es el responsable de la ejecución desatendida. Contiene una lista de horarios (`schedule`) donde se definen:
- **Cuándo**: Ej. (1, 0) para la 1:00 AM.
- **Qué**: Ej. `run_descargas_yesterday`.
- **Lógica**: El scheduler llama a `enqueue_task`, que pone la orden en la cola de Redis.

### B. La API (`api/routes/*.py`) - **Manual**
Los usuarios o sistemas externos pueden forzar una ejecución llamando a los endpoints (ej. `/api/descargas/trigger`). Esto permite pasar parámetros específicos (un cliente concreto, una fecha específica).

---

## 2. ¿Dónde está la lógica de selección? (El "Criterio")

La inteligencia sobre **qué clientes** o **qué notificaciones** deben procesarse NO está en el código Python de los robots, sino en la **Capa de Base de Datos (SQL Server)**.

### La Fuente de la Verdad: SQL Queries
Cada dominio tiene sus propias consultas en `database/<dominio>/queries/`.

#### Ejemplo: Descargas (`getNotificacionesPendientes.py`)
Esta consulta es el corazón de las descargas. Decide qué procesar basándose en:
1.  **Servicios Activos**: Mira la tabla `info.beneficiariobonos` buscando servicios como 'SUSCRIPCION', 'NEO', o 'BLINDAJE' que no hayan caducado.
2.  **Estado de Cobro**: Solo selecciona clientes con situación 'COBRADO', 'PENDIENTE VT' o 'ESPECIAL HP'.
3.  **Certificados Válidos**: Cruza con `certificates_managements_` para asegurar que el certificado está 'Vigente' y 'Completado'.
4.  **Estado de la Notificación**: Solo busca en `emails_messages` aquellas con `status_id` que signifique 'Pendiente' o 'Agencia Tributaria'.
5.  **Filtro de Fecha**: Normalmente busca lo llegado ayer, a menos que se fuerce otra fecha.

**Ubicación del archivo:** `database/descargas/queries/getNotificacionesPendientes.py`

---

## 3. ¿Cómo se saca la información? (El Proceso de Extracción)

La extracción ocurre en dos fases claramente diferenciadas:

### Fase 1: Extracción de Metadatos (SQL)
1. El `DatabaseManager` ejecuta la consulta SQL mencionada arriba.
2. SQL Server devuelve una lista de registros. Cada registro contiene:
   - `client_id` (Quién es el cliente).
   - `message_key` (El ID único de la notificación en el sistema).
   - `sede` (A qué portal hay que ir: Dehú, e-Notum, DGT).
   - `body_html` (El contenido del email original para parsear el expediente).

### Fase 2: Envío al Dispatcher
Una vez que el sistema tiene los registros de la Fase 1:
1. **Batching**: Se agrupan los registros para optimizar la carga de trabajo.
2. **Encolado**: Se inyecta un JSON con los parámetros de los items en la `dispatcher_tasks_queue` de Redis.
3. **Orquestación**: El Dispatcher toma este mensaje y busca el mejor worker disponible basándose en métricas de hardware y carga.

---

## 4. Resumen de Ubicaciones Críticas

| Pregunta | Respuesta | Ubicación en el Código |
| :--- | :--- | :--- |
| **¿Quién decide el horario?** | El Scheduler | `api/scheduler.py` |
| **¿Quién decide qué clientes?** | Consultas SQL | `database/*/queries/*.py` |
| **¿Quién orquesta el envío?** | Dispatcher | `api/dispatcher.py` |
| **¿Dónde se guarda el log de asignación?** | Database Manager | `database/database_manager.py` |

---

Este diseño permite cambiar las reglas de negocio (ej. "ahora solo descargamos a clientes VIP") simplemente modificando una consulta SQL, sin necesidad de tocar el código de los robots o del dispatcher.
