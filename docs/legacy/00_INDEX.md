# RedTrust Automation Docs

## Objetivo

Esta carpeta documenta el repositorio como un sistema operativo completo, no solo como código fuente. La idea es poder entender cómo se ejecuta, qué piezas lo forman, cómo se relacionan y dónde intervenir sin volver a recorrer el repositorio entero.

## Mapa de lectura recomendado

1. `01_SYSTEM_OVERVIEW.md`
2. `02_API_SURFACE.md`
3. `03_TASK_ORCHESTRATION.md`
4. `04_REDIS_AND_RUNTIME_STATE.md`
5. `05_DATABASE_LAYER.md`
6. Documentos por dominio de robot:
   - `06_ALTAS_DOMAIN.md`
   - `07_DESCARGAS_DOMAIN.md`
   - `08_CONSULTA_ENOTUM_DOMAIN.md`
   - `09_MATRICULAS_PUNTOS_DOMAIN.md`
   - `10_SEDE_JUDICIAL_DOMAIN.md`
7. Soporte transversal:
   - `11_CERTIFICATES_AND_REDTRUST.md`
   - `12_OBSERVABILITY_AND_OPERATIONS.md`
   - `13_ROBOT_CATALOG.md`

## Qué es este proyecto

RedTrust Automation es una plataforma de automatización híbrida:

- La entrada es una API FastAPI.
- La coordinación de trabajo se hace con Redis + un dispatcher propio.
- La ejecución remota la hacen workers Celery.
- La automatización de negocio vive en robots RPA Python con Selenium/pywinauto/automatización GUI.
- El estado funcional y el histórico persisten en SQL Server.
- RedTrust y el selector de certificados son una dependencia operativa crítica.

## Componentes troncales

- `api/server.py`: nodo master de la aplicación.
- `api/dispatcher.py`: decide qué worker debe recibir cada tarea.
- `api/enqueuer.py`: escribe tareas en la cola del dispatcher.
- `api/worker.py`: inicializa Celery, publica heartbeat y ejecuta robots.
- `api/scheduler.py`: ejecuta automatizaciones programadas.
- `database/`: capa de acceso a SQL Server por dominio.
- `app/robot_*.py`: orquestadores principales de cada familia de robots.
- `app/robot/*`: implementaciones portal-específicas.
- `app/redtrust/redtrust_manager.py`: carga de certificados en RedTrust.
- `app/robot/handle_certificate.py`: interacción con el popup nativo de selección de certificado.

## Advertencias operativas

- El directorio físico `/docs` convive con la documentación Swagger de FastAPI configurada en `docs_url="/docs"`.
- La plataforma depende de entorno gráfico, ventanas del sistema, certificados vigentes y conectividad hacia portales externos.
- Hay mezcla de patrones: parte de la coordinación está en Celery y parte en infraestructura propia sobre Redis.
