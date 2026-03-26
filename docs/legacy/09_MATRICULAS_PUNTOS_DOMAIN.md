# Dominio de Matrículas y Puntos

## Propósito

Obtiene informes DGT para clientes, extrae matrículas, puntos, alertas y persiste resultados enriquecidos.

## Orquestador principal

`app/robot_matriculas_y_puntos.py` con la clase `RobotMatriculasYPuntos`.

## Flujo funcional

1. Recupera clientes aptos desde `InformesDgtDatabase.fetch_dev_clientes`.
2. Excluye clientes marcados en `error_clients.txt`.
3. Procesa clientes en bloques de 3.
4. Carga certificado DGT en RedTrust.
5. Maneja la ventana de selección de certificado.
6. Ejecuta `RobotDgt.informeDgt(...)`.
7. Persiste informe, matrículas, alertas y puntos.
8. Actualiza histórico.

## Robot específico

- `app/robot/matriculasypuntos/robotDgt.py`

## Fuente funcional

El scheduler usa este dominio para:

- ejecución nocturna estándar
- proceso `Data 360`

## Persistencia rica

`InformesDgtDatabase` contiene:

- `fetch_dev_clientes`
- `insert_matriculas`
- `insert_puntos`
- `update_historico_informesDgt`

## Datos que genera

- informe DGT principal
- vehículos o matrículas
- alertas por vehículo
- sanciones
- puntos del conductor

## Riesgos

- persistencia compleja y sensible a cambios de esquema
- acoplamiento entre salida del robot DGT y estructura SQL
