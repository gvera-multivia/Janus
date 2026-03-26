# Guía 01: Infraestructura para el Dispatcher

Esta guía detalla los componentes de infraestructura necesarios exclusivamente para el funcionamiento del **Dispatcher** como orquestador central.

---

## 1. Redis: El Bus de Control

Redis es el motor que permite al Dispatcher comunicarse con el mundo exterior y con los workers sin acoplamiento directo.

### A. Cola de Tareas (`dispatcher_tasks_queue`)
- **Estructura**: Lista.
- **Función**: Almacén persistente de peticiones de trabajo pendientes.
- **Dato**: Objetos JSON con metadatos de la tarea (tipo, parámetros, prioridad).

### B. Registro de Estado (Heartbeats)
- **Patrón**: `worker_status:{id}`.
- **Contenido**: Métricas de salud enviadas por los trabajadores (CPU, Memoria, Disponibilidad).
- **Importancia**: Permite al Dispatcher saber quién está "vivo" antes de asignar.

### C. Bloqueo de Asignación (Mutex)
- **Patrón**: `task_assignment:{task_id}`.
- **Valor**: ID del worker asignado.
- **TTL**: Evita que una tarea quede bloqueada para siempre si un worker muere.

---

## 2. SQL Server: El Almacén de Criterios

Aunque el Dispatcher vive en Redis, necesita de SQL Server para dos funciones críticas de orquestación:

1.  **Criterios de Elegibilidad**: Consultas complejas que deciden qué items (clientes/notificaciones) están listos para ser procesados hoy.
2.  **Registro Histórico**: Tabla `automations_assignment_log` para que el Dispatcher pueda calcular el balanceo de carga basándose en cuántas tareas ha recibido cada worker recientemente.

---

## 3. Variables de Configuración

Para replicar el Dispatcher se necesitan:
- `REDIS_HOST/PORT`: Ubicación del bus.
- `WORKER_TIMEOUT`: Tiempo tras el cual el Dispatcher considera a un worker "muerto" (ej. 30s).
- `TASK_ASSIGNMENT_EXPIRE`: Tiempo de validez de la reserva de tarea.
- `MAX_RETRIES`: Número de intentos de asignación antes de devolver la tarea a la cola.
