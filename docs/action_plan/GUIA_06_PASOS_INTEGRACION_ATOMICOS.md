# Guía 06: Plan de Acción - Integración Total y Atómica Dispatcher ↔ Robot

Esta guía desglosa la integración en **tareas atómicas y concretas**. Siguiendo estos pasos, un desarrollador puede transformar cualquier script local (como `dehu_automation/main.py`) en un worker integrado en el ecosistema del Dispatcher, sin necesidad de investigar el resto del código fuente.

---

## Fase 1: Adaptación de la Entrada (Eliminar Local)

El objetivo es que el robot deje de leer `clientes.json` o `sys.argv` y pase a recibir un diccionario Python (`kwargs`) inyectado por el orquestador.

- [ ] **Tarea 1.1: Eliminar dependencias locales en `main.py`**
  - Borrar o comentar la lógica que carga el archivo `clientes.json`.
  - Borrar o comentar el uso de `sys.argv` para cargar rutas de archivos.
  - Eliminar o adaptar la función `build_legacy_local_job`.

- [ ] **Tarea 1.2: Crear el "Entrypoint" del Worker**
  - Crear una nueva función principal (ej. `run_automation_task(task_id, **kwargs)`).
  - Extraer los parámetros obligatorios del diccionario `kwargs`:
    ```python
    def run_automation_task(task_id, **kwargs):
        job_id = kwargs.get("job_id")
        sede = kwargs.get("sede")
        raw_clients = kwargs.get("clientes")

        if not sede or not raw_clients:
            raise ValueError("Faltan 'sede' o 'clientes' en el payload")
    ```

- [ ] **Tarea 1.3: Instanciar el procesador correcto (Factory)**
  - Usar la variable `sede` extraída en el paso anterior para instanciar el proceso específico:
    ```python
    process_site_client = get_site_processor(sede)
    ```

---

## Fase 2: Conexión con Redis (Estado en Vivo)

El robot debe comunicarse con Redis para notificar al Dispatcher cuándo empieza, cómo avanza y cuándo termina. Se asume la existencia de una clase `RedisManager` en la API.

- [ ] **Tarea 2.1: Notificar inicio de tarea**
  - Al principio de `run_automation_task`, llamar a Redis para indicar que el worker ha comenzado a trabajar.
  - *Acción:* Ejecutar `redis_manager.register_task_start(task_id, task_name="run_generic_robot", worker_id=mi_ip_o_hostname, ...)`

- [ ] **Tarea 2.2: Modificar el bucle de clientes (`run_client_batch`) para reportar progreso**
  - Dentro de la función que itera sobre `raw_clients` (ej. `core/runner.py`), añadir una llamada en cada iteración.
  - Calcular el porcentaje: `(index / total_clients) * 100`.
  - *Acción:* Ejecutar `redis_manager.publish_task_progress(task_id, porcentaje, mensaje="Procesando cliente X")`.

- [ ] **Tarea 2.3: Notificar fin de tarea**
  - Al final de `run_automation_task` (tanto si acaba bien como si lanza excepción), notificar el resultado.
  - *Acción:* En un bloque `try/finally`, ejecutar `redis_manager.register_task_end(task_id, worker_id=mi_ip, status="completed" o "failed")`.

---

## Fase 3: Integración con Celery (Convertirse en Worker)

El robot necesita "escuchar" la cola del Dispatcher usando Celery.

- [ ] **Tarea 3.1: Definir la tarea Celery (`@app.task`)**
  - En un archivo (ej. `worker.py` o dentro del mismo robot si es monolito), configurar Celery:
    ```python
    from celery import Celery
    app = Celery('robot_system', broker='redis://...', backend='redis://...')

    @app.task(name="run_generic_robot", bind=True)
    def celery_run_automation(self, *args, **kwargs):
        task_id = self.request.id or kwargs.get("task_id")
        # Aquí se llama a la función de la Fase 1
        return run_automation_task(task_id, **kwargs)
    ```

- [ ] **Tarea 3.2: Configurar el consumo de colas**
  - Asegurar que el worker de Celery escucha específicamente en la cola que el Dispatcher utiliza (por defecto, `robot_tasks`).
  - *Acción:* Arrancar Celery con `celery -A worker app worker -Q robot_tasks --concurrency=1`.

---

## Fase 4: Persistencia (Base de Datos)

El robot local generaba un `resultados_clientes.json`. En producción, debe insertar en SQL.

- [ ] **Tarea 4.1: Eliminar escritura de JSON local**
  - Borrar o comentar la llamada a `save_results_to_json(...)` al final del proceso.

- [ ] **Tarea 4.2: Escribir en Base de Datos (SQL)**
  - En lugar de guardar un archivo JSON, iterar sobre la lista de resultados finales.
  - Por cada cliente procesado (Altas, Errores), ejecutar un `INSERT` o `UPDATE` en la tabla histórica correspondiente (ej. `historico_automatizaciones`).
  - *Acción:* Usar el conector/ORM configurado en el proyecto para persistir los estados devueltos por `run_client_batch`.

---

## Resumen del Flujo Final Integrado

1. **Celery Worker** arranca y se queda escuchando `robot_tasks`.
2. **Dispatcher** envía un mensaje a Celery con nombre `run_generic_robot` y el payload opaco `kwargs`.
3. Celery recibe el mensaje e invoca `celery_run_automation`.
4. El robot marca en Redis: *"He empezado la tarea X"*.
5. El robot extrae `sede`, carga el driver de esa sede e itera sobre `clientes`.
6. Por cada cliente, el robot notifica a Redis: *"Voy por el 25%"*.
7. El robot termina, guarda todo en SQL y avisa a Redis: *"He terminado la tarea X con éxito"*.
