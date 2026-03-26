# Guía 03: Arquitectura Interna del Dispatcher

Esta es la guía técnica definitiva sobre el bucle interno, la lógica de decisión y el protocolo de seguridad del Dispatcher.

---

## 1. El Bucle de Distribución (Internal Loop)

El Dispatcher corre en un loop infinito con el siguiente flujo de trabajo:

```python
while running:
    # 1. Escucha bloqueante o periódica
    task = redis.lpop('dispatcher_tasks_queue')

    if task:
        # 2. Análisis de recursos globales
        workers = get_alive_workers() # Mira en worker_status:*

        # 3. Selección inteligente
        best_worker = select_best_worker(workers, task)

        if best_worker:
            # 4. Fase de Reserva (Crítica)
            reserve_task(task['id'], best_worker['id'])

            # 5. Despacho
            dispatch_to_broker(task, best_worker)
        else:
            # 6. Manejo de saturación
            requeue_task(task)
            sleep(10) # Espera a que se liberen recursos
```

---

## 2. El Algoritmo de Scoring (Cerebro del Dispatcher)

Para decidir a quién enviar la tarea, el Dispatcher aplica una fórmula ponderada:

| Factor | Peso | Lógica |
| :--- | :--- | :--- |
| **CPU Libre** | 40% | `(100 - cpu_usage)` |
| **RAM Libre** | 30% | `(100 - mem_usage)` |
| **Carga Reciente** | 30% | Penaliza si el worker ha recibido >N tareas en la última hora. |

---

## 3. El Protocolo de Reserva Atómica

Para asegurar que **NUNCA** dos workers procesen lo mismo bajo ninguna circunstancia, el Dispatcher usa un sistema de reserva en Redis:

1.  **SET con NX**: `SET task_assignment:{task_id} {worker_id} NX EX 14400`.
    - Si el comando devuelve `True`, el Dispatcher ha ganado el derecho de asignar esa tarea.
2.  **Verificación del Worker**: El worker, antes de hacer nada, debe hacer un `GET task_assignment:{task_id}`.
    - Si el ID guardado no es el suyo, el worker **DEBE ABORTAR** inmediatamente.

---

## 4. Gestión de Fallos del Dispatcher

- **Zombie Workers**: Si un worker desaparece sin avisar, el Dispatcher limpia su `worker_status` tras el timeout configurado.
- **Tareas Huérfanas**: Si una tarea se reserva pero el worker muere antes de empezar, el TTL de Redis liberará la tarea automáticamente para que pueda ser re-encolada por un proceso de auditoría.
