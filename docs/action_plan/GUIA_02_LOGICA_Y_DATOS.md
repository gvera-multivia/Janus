# Guía 02: Preparación de Datos para el Dispatcher

El Dispatcher no genera datos, los orquestas. Esta guía explica cómo alimentar correctamente al Dispatcher desde el "Cerebro SQL".

---

## 1. El Generador de Tareas (Scheduler/API)

Cualquier sistema que quiera usar el Dispatcher debe seguir el protocolo de encolado:

1.  **Consulta SQL**: Se ejecuta una query que extrae los items pendientes.
2.  **Agrupación (Batching)**: Si hay 1000 items, no es eficiente crear 1000 tareas. El sistema agrupa items por criterios comunes (ej. mismo cliente o misma sede).
3.  **Encapsulamiento**: Se crea un JSON con:
    - `task_id`: UUID único.
    - `task_name`: Identificador del tipo de trabajo.
    - `kwargs`: Los datos específicos (lista de IDs a procesar).

---

## 2. El Contrato de Interfaz (El Mensaje)

Para que el Dispatcher pueda orquestar, el mensaje en `dispatcher_tasks_queue` debe ser consistente:

```json
{
  "task": "run_robot_descargas",
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "args": [],
  "kwargs": {
    "ids": [1, 2, 3, 4],
    "priority": "high"
  },
  "enqueued_at": 1710000000
}
```

---

## 3. Lógica de "Limpieza de Entrada"

Antes de que el Dispatcher vea la tarea, el componente que encola debe validar:
1.  **Deduplicación**: No encolar la misma tarea si ya hay una idéntica esperando.
2.  **Priorización**: El Dispatcher procesa en orden FIFO, pero se pueden implementar múltiples colas (`high_priority_queue`) si el negocio lo requiere.
