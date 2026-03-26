# Guía 04: Plan de Acción - Replicación del Dispatcher

Este plan de acción se centra exclusivamente en la construcción y despliegue del componente **Dispatcher**, ignorando la lógica de ejecución de los jobs finales.

---

## Fase 1: Infraestructura y Bus de Datos (Días 1-3)

El objetivo es tener el canal de comunicación listo.

1.  **Despliegue de Redis**: Configurar una instancia de Redis persistente.
2.  **Definición de Esquema de Colas**: Crear las colas de entrada y las estructuras de prefijos para `worker_status` y `task_assignment`.
3.  **Simulador de Entrada**: Crear un script simple que inserte tareas JSON en `dispatcher_tasks_queue` para probar el flujo.

---

## Fase 2: El Motor de Decisión (Días 4-8)

Construcción del núcleo lógico del Dispatcher.

1.  **Módulo de Descubrimiento**: Desarrollar la lógica que lee los heartbeats de Redis y devuelve una lista de workers activos y sus métricas.
2.  **Algoritmo de Selección**: Implementar la lógica de scoring (CPU, RAM, carga histórica) para elegir el mejor destino.
3.  **Protocolo de Reserva Atómica**: Programar la escritura en Redis con el flag `NX` para asegurar la exclusividad de la asignación.
4.  **Bucle Principal**: Integrar todo en un loop infinito robusto que maneje excepciones sin detenerse.

---

## Fase 3: Interfaz y Alimentación (Días 9-12)

Conectar el "Cerebro SQL" con el Dispatcher.

1.  **Módulo de Consulta SQL**: Desarrollar las queries que extraen los items candidatos desde SQL Server.
2.  **Lógica de Batching**: Implementar el agrupador que convierte miles de registros de DB en unas pocas decenas de tareas para el Dispatcher.
3.  **API de Control**: Crear un endpoint (FastAPI/Node) que permita pausar, reanudar o vaciar la cola del Dispatcher manualmente.

---

## Fase 4: Resiliencia y Monitoreo (Días 13-15)

Asegurar que el Dispatcher es de grado de producción.

1.  **Manejo de Tareas Huérfanas**: Crear un proceso que busque tareas reservadas cuyo TTL haya expirado y las devuelva a la cola.
2.  **Dashboard de Orquestación**: (Opcional) Visualizar en tiempo real cuántas tareas hay en cola y qué worker tiene asignada cada una.
3.  **Pruebas de Carga**: Simular 100 workers enviando heartbeats simultáneos y verificar que el scoring responde en milisegundos.

---

## Checklist de Éxito del Dispatcher
- [ ] ¿Puede el Dispatcher manejar el caso de "0 workers disponibles" sin morir?
- [ ] ¿Se respeta la reserva atómica en Redis para evitar duplicidad?
- [ ] ¿El algoritmo de scoring prioriza correctamente a los workers menos cargados?
- [ ] ¿Es el Dispatcher independiente del lenguaje en el que estén escritos los workers?
