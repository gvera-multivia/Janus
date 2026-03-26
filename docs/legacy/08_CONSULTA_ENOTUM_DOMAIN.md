# Dominio de Consulta eNotum

## Propósito

Realiza consultas sobre eNotum, revisa notificaciones y transforma el resultado en registros útiles para seguimiento posterior.

## Orquestador principal

`app/robot_consulta_enotum.py` con la clase `RobotConsultaEnotum`.

## Flujo funcional

1. Consulta clientes y notificaciones pendientes mediante `ConsultasDatabase`.
2. Estructura y filtra notificaciones.
3. Extrae y valida servicios activos.
4. Carga certificado.
5. Ejecuta el robot de consulta eNotum.
6. Recoge resultados de consulta.
7. Actualiza histórico y estado de la consulta.

## Robot específico

- `app/robot/consultas/robotEnotum.py`

## Funciones relevantes

- `structure_and_filter_notifications`
- `extract_and_validate_service_info`
- `consultar_sede`
- `run`

## Diferencia respecto a descargas

- comparte mecánicas de certificado y portal
- el foco es consulta y revisión de eNotum
- el resultado funcional puede ser “sin notificaciones”, “login error” o un conjunto de resultados

## Dependencias transversales

- `RedTrustManager`
- `CertificateManager`
- `ConsultasDatabase`
- modelos de consulta y notificación

## Riesgos

- alta sensibilidad a cambios en el portal eNotum
- posible confusión operativa si se mezcla con descargas en reporting
