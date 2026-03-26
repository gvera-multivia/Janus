# Dominio de Sede Judicial

## Propósito

Consulta la sede judicial, inspecciona expedientes y persiste una estructura judicial completa para cada cliente.

## Orquestador principal

`app/robot_sede_judicial.py` con la clase `RobotSedeJudicial`.

## Flujo funcional

1. Recupera clientes elegibles desde `SedeJudicialDatabase.fetch_sedejudicial`.
2. Calcula progreso.
3. Carga certificado en RedTrust.
4. Gestiona el selector de certificado.
5. Ejecuta `RobotSeuJudicialGencat.inspect()`.
6. Convierte el resultado en modelos estrictos con `_build_db_models`.
7. Persiste:
   - resumen de automatización
   - expedientes
   - señalamientos
   - justicia gratuita
   - hitos
   - intervinientes
   - otros procedimientos

## Robot específico

- `app/robot/sedejudicial/RobotSeuJudicialGencat.py`

## Particularidades

- Es el dominio con modelo relacional más jerárquico.
- `_build_db_models` hace conversión explícita de fechas, decimales y UUIDs.

## Persistencia

`database/sedejudicial/database_sedejudicial.py`:

- `fetch_sedejudicial`
- `update_historico_sedejudicial`

## Riesgos

- transacciones largas y múltiples commits
- mucha estructura implícita en el payload del robot
