# Dominio de Descargas

## Propósito

Automatiza la localización, filtrado, descarga y validación de notificaciones y documentos para distintos canales administrativos.

## Orquestador principal

`app/robot_descargas.py` con la clase `RobotDescargas`.

## Flujo funcional

1. Recupera notificaciones pendientes desde `DescargaDatabase.fetch_notifications`.
2. Estructura notificaciones por cliente y por sede.
3. Valida si el servicio del cliente permite procesar esa notificación.
4. Normaliza el cuerpo del mensaje mediante el robot específico.
5. Carga certificado en RedTrust.
6. Maneja el popup de selección de certificado.
7. Ejecuta el robot del portal para descargar notificaciones en lote.
8. Interpreta `DescargaResult`.
9. Actualiza estado de la notificación e histórico.

## Entradas soportadas

- fecha
- cliente
- sedes
- `message_ids`
- `message_keys`
- límite

## Canales soportados

- Dehú
- eNotum
- DGT/DEV

Robots específicos:

- `app/robot/descargas/robotDehu.py`
- `app/robot/descargas/robotEnotum.py`
- `app/robot/descargas/robotDgt.py`

## Normalización de negocio

`extract_and_validate_service_info`:

- valida `servicio`
- calcula servicios vigentes por fecha
- fusiona `SUSCRIPCION + INFONEO -> MULTINEO` cuando aplica
- parsea el `body_html` con el robot correspondiente

## Estados funcionales de notificación

En `update_notification_status` aparecen IDs relevantes:

- `1` pendiente
- `2` descargado
- `7` sin servicios NEO
- `9` agencia tributaria
- `11` sólo suscripción
- `14` no descargar nada

## Scheduler relacionado

Este dominio es el más automatizado por horario:

- descargas del día anterior
- descargas retroactivas
- limpieza por lotes de `message_keys`

## Riesgos

- mezcla de reglas de negocio, parsing y RPA
- mucha lógica condicional por sede
- estado final disperso entre `emails_messages`, histórico y ficheros
