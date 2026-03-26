# Dominio de Altas

## Propósito

Automatiza el alta o suscripción de clientes en múltiples sedes administrativas usando su certificado digital.

## Orquestador principal

`app/robot_altas.py` con la clase `RobotAltas`.

## Flujo funcional

1. Obtiene altas pendientes desde `AltasDatabase.fetch_altas`.
2. Estructura las altas por cliente y sedes.
3. Calcula progreso global.
4. Carga certificados en RedTrust.
5. Lanza procesos paralelos:
   - manejo del popup de certificado
   - robot del portal correspondiente
6. Recoge resultado por sede.
7. Actualiza tablas funcionales e histórico.

## Fases de progreso

- `db_fetch`
- `estructuracion`
- `asignacion_certificados`
- `carga_certificados`
- `ejecucion_tarea`
- `finalizado`

## Robots específicos de altas

`app/robot/altas/` contiene implementaciones portal-específicas:

- Andalucía
- Asturias
- ATC
- Ayuntamiento de Málaga
- Badajoz
- Baleares
- Burgos
- Castilla-La Mancha
- Castilla y León
- Ceuta
- Comunidad Valenciana
- Dehú
- DGT
- eNotum
- La Rioja
- Madrid
- Mahón
- Melilla
- Migjorn Gran
- País Vasco
- Terrassa
- Xaloc

## Selección de robot

La selección depende del string `sede`. `RobotAltas` mantiene un mapa `sede -> clase de robot`.

## Particularidades

- `run_portal_robot_static` adapta la firma del método `subscribe` según la sede.
- No todas las sedes devuelven la misma forma de resultado.
- Algunas sedes devuelven `check, action`; otras `check, action, email`.

## Dependencias transversales

- `RedTrustManager`
- `CertificateManager`
- `LoggerV2`
- `AltasDatabase`

## Qué persiste

- actualización de estado en `certificates_sedes`
- alertas sobre certificado si procede
- histórico unificado de ejecución

## Riesgos

- fuerte acoplamiento entre nombre de sede y firma esperada del robot
- contratos de retorno heterogéneos
- errores de UI o certificado pueden dejar alta parcialmente tratada
