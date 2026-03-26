# Catálogo de Robots y Automatizaciones

## Robots orquestadores

- `RobotAltas`
- `RobotDescargas`
- `RobotConsultaEnotum`
- `RobotMatriculasYPuntos`
- `RobotSedeJudicial`

## Robots específicos de altas

- `robotAndalucia`
- `robotAsturias`
- `robotAtc`
- `robotAyuntamientoMalaga`
- `robotBadajoz`
- `robotBaleares`
- `robotBurgos`
- `robotCastillaLaMancha`
- `robotCastillaLeon`
- `robotCeuta`
- `robotComunidadValenciana`
- `robotDehu`
- `robotDgt`
- `robotEnotum`
- `robotLaRioja`
- `robotMadrid`
- `robotMahon`
- `robotMelilla`
- `robotMigjornGran`
- `robotPaisVasco`
- `robotTerrassa`
- `robotXaloc`

## Robots específicos de descargas

- `robotDehu`
- `robotDgt`
- `robotEnotum`

## Robots específicos de consultas

- `consultas/robotEnotum`

## Robots específicos de matrículas y puntos

- `matriculasypuntos/robotDgt`

## Robots específicos de sede judicial

- `sedejudicial/RobotSeuJudicialGencat`

## Automatizaciones programadas conocidas

- Descargas diarias
- Descargas retroactivas
- Limpieza de descargas
- Altas por defecto
- Matrículas por defecto
- Consulta eNotum
- Data 360

## Cómo ampliar el sistema

Para añadir una automatización nueva normalmente hay que tocar:

1. robot específico en `app/robot/...`
2. mapa de selección en el orquestador
3. reglas de `CertificateManager.SITES`
4. capa de base de datos si el resultado necesita persistencia nueva
5. API o scheduler si requiere exposición o ejecución periódica
