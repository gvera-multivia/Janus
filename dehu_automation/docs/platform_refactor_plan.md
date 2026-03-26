# Plan de Evolución hacia una Plataforma Multi-sede

## 1. Visión general

### Objetivo

Evolucionar el sistema actual, hoy centrado en DEHú, hacia una plataforma reutilizable capaz de ejecutar automatizaciones similares sobre múltiples sedes, por ejemplo:

- `dehu`
- `dgt`
- otras sedes futuras con login por certificado y flujo web comparable

La idea no es rehacer el sistema ni convertirlo en una arquitectura grande, sino separar de forma clara:

- lo común a cualquier sede
- lo específico de cada sede

### Cambio respecto al sistema actual

Hoy el proyecto está organizado alrededor de un flujo concreto de DEHú:

- selección de certificado con RedTrust
- arranque de Edge
- login con certificado
- validación del login
- alta de email
- logout
- guardado de resultados

La evolución propuesta consiste en mantener ese flujo como base, pero encapsular la lógica específica de DEHú dentro de una capa “site-specific”, de forma que el resto del sistema pueda reutilizarse para otras sedes sin duplicar orquestación, resultados, logging, evidencias o gestión del navegador.

## 2. Principios clave

### Ejecución controlada

- Mantener un modelo de ejecución secuencial por cliente.
- Mantener un número de workers muy limitado al principio, idealmente uno.
- Evitar paralelismo agresivo con UI Automation, Edge o certificados.

### Simplicidad

- No introducir frameworks nuevos si no resuelven un problema real.
- Evitar patrones abstractos si solo van a tener una implementación durante mucho tiempo.
- Preferir funciones y objetos pequeños antes que jerarquías complejas.

### Reutilización real

- Compartir solo lo que realmente se repite entre sedes.
- Mantener la lógica específica de cada sede aislada, sin contaminar el core.
- No forzar una interfaz genérica artificial si todavía no se conocen bien los casos futuros.

### Compatibilidad con el sistema actual

- El flujo actual de DEHú debe poder seguir funcionando durante la transición.
- La migración debe hacerse por fases, no mediante un reemplazo total.
- `main.py` puede actuar inicialmente como runner local mientras se extrae el core.

### Observabilidad desde el inicio

- Mantener resultados estructurados.
- Mantener evidencias y tiempos por cliente.
- Añadir trazabilidad por job sin romper la trazabilidad actual por cliente.

## 3. Separación de responsabilidades

### A. Core común

Estas piezas deberían ser compartidas entre todas las sedes:

#### Modelo de cliente

Datos de entrada comunes:

- `nif`
- `nombre`
- `email`
- `id_redtrust`

Se puede ampliar en el futuro con campos opcionales por sede, pero el núcleo debería seguir siendo común.

#### Modelo de resultado

Resultado estructurado por cliente:

- `resultado`
- `mensaje`
- `fase_error`
- `url_error`
- `captura_error`
- timestamps
- duración
- intento

El objetivo es conservar un contrato de salida homogéneo.

#### Ejecución por cliente

Responsabilidad común:

- validar entrada
- preparar contexto de ejecución
- invocar RedTrust si aplica
- arrancar navegador
- delegar en la sede concreta
- registrar resultado
- cerrar recursos

#### Integración con RedTrust

RedTrust seguirá siendo un servicio o componente compartido:

- selección/preselección de certificado
- bridge/subprocess
- automatización UIA específica de RedTrust

Esto no debería duplicarse por sede.

#### Arranque de navegador

Parte común:

- Edge
- perfil temporal
- remote debugging
- conexión Playwright
- intento de foco nativo

La sede no debería gestionar el arranque base del navegador.

#### Manejo de errores

Responsabilidades comunes:

- clasificación consistente
- captura de evidencias
- tiempos
- trazabilidad
- política de reintentos por resultado

#### Logging y evidencias

Común para todo el sistema:

- logger compartido
- capturas
- estructura JSON de resultados
- futura asociación entre job y resultados por cliente

### B. Lógica específica por sede

Estas piezas deben vivir dentro de cada sede:

- URL inicial
- navegación Playwright
- selectores
- flujo de login
- validación de login
- flujo funcional principal
- validaciones específicas
- logout si cambia por sede

#### Ejemplo DEHú

En DEHú hoy son específicas:

- acceso a `https://dehu.redsara.es/es/public`
- click en `Acceder a DEHu`
- click en `Acceso DNIe / Certificado`
- validación de login basada en URL o señales de la página
- acceso a `Datos de contacto`
- alta de correo
- logout en el menú de perfil

#### Ejemplo DGT

Si mañana se automatiza DGT, deberían cambiar solo:

- URL
- navegación
- validación de sesión
- operación funcional de negocio
- logout específico

Pero deberían reutilizarse:

- el modelo de entrada
- RedTrust
- Edge/Playwright base
- resultados
- reintentos
- evidencias

## 4. Concepto de “Job”

Un `job` representa una ejecución completa sobre una sede concreta y una lista de clientes.

### Campos propuestos

- `job_id`
- `sede`
- `clientes`
- `estado`
- `timestamp_creacion`
- `timestamp_inicio`
- `timestamp_fin`
- `metadata` opcional

### Estados de job propuestos

- `pending`
- `running`
- `completed`
- `completed_with_errors`
- `failed`
- `cancelled`

### Ejemplo JSON

```json
{
  "job_id": "job_2026-03-25_001",
  "sede": "dehu",
  "estado": "pending",
  "timestamp_creacion": "2026-03-25T15:00:00",
  "timestamp_inicio": null,
  "timestamp_fin": null,
  "clientes": [
    {
      "nif": "12345678A",
      "nombre": "Maria Louders",
      "email": "lourdes@email.com",
      "id_redtrust": "43534 -"
    },
    {
      "nif": "19865678C",
      "nombre": "Juan",
      "email": "juan@gmail.com",
      "id_redtrust": "28751 -"
    }
  ],
  "metadata": {
    "source": "local_json"
  }
}
```

### Relación entre job y resultados

El job agrupa la ejecución.

Los resultados por cliente deberían seguir guardándose con la misma granularidad actual, pero en el futuro asociados además a:

- `job_id`
- `sede`

## 5. Modelo de ejecución

### Worker único o controlado

La propuesta inicial es:

- un único worker local
- una sola ejecución activa a la vez
- procesamiento secuencial de clientes

Esto encaja mejor con:

- RedTrust
- foco de Edge
- popup de certificado
- automatización de escritorio

### Cola de trabajos

No se propone implementar una cola real todavía.

Conceptualmente, el sistema debería poder evolucionar a:

- lista de jobs pendientes
- worker que toma el siguiente job
- ejecución secuencial por job y por cliente

### Estados de cliente

Cada cliente dentro de un job puede pasar por estados conceptuales como:

- `pending`
- `running`
- `completed`
- `failed`
- `retry_pending`
- `retried`

No hace falta implementar todos estos estados hoy, pero sirven para definir la semántica futura.

## 6. Arquitectura propuesta

La estructura objetivo debería ser sencilla y cercana al sistema actual.

### Estructura de carpetas propuesta

```text
core/
  models/
    cliente.py
    job.py
    result.py
  runner/
    client_runner.py
    job_runner.py
  retries/
    retry_policy.py
  evidence/
    capture.py
  errors/
    result_builder.py

shared/
  browser/
    edge_browser.py
  certificates/
    redtrust_bridge.py
    redtrust_window_inspect.py
  logging/
    logger.py

sites/
  dehu/
    site.py
    playwright_flow.py
  dgt/
    site.py
    playwright_flow.py

worker/
  local_worker.py

inputs/
  jobs/

outputs/
  results/
  artifacts/

main.py
```

### Sentido de cada bloque

- `core/`
  Orquestación común, modelos y ejecución.

- `shared/`
  Componentes compartidos entre sedes:
  navegador, certificados, logging.

- `sites/`
  Implementaciones específicas de cada sede.

- `worker/`
  Runner local que toma un job y lo ejecuta.

- `inputs/` y `outputs/`
  Persistencia básica de jobs y resultados si se quiere desacoplar de la raíz del proyecto.

### Compatibilidad con el estado actual

La migración natural sería:

- lo actual de `browser/`, `certificates/` y `utils/` pasaría a `shared/`
- la lógica de `dehu/dehu_automation.py` pasaría a `sites/dehu/`
- `main.py` acabaría actuando como punto de entrada de un worker local o runner de jobs

## 7. Fases de implementación

## Fase 1 — Refactorizar DEHú como primera sede

Objetivo:

- separar el flujo específico de DEHú del core común

Resultado esperado:

- DEHú sigue funcionando igual
- se define una interfaz mínima para una sede
- la orquestación común deja de estar acoplada a DEHú

Alcance razonable:

- extraer modelos comunes
- extraer ejecución común por cliente
- encapsular la lógica web de DEHú como primera implementación de sede

## Fase 2 — Runner local con jobs

Objetivo:

- dejar de pensar solo en `clientes.json`
- empezar a pensar en ejecuciones agrupadas como jobs

Resultado esperado:

- un runner local recibe un job
- procesa sus clientes
- guarda resultados asociados al job

Sin introducir todavía:

- colas reales
- workers múltiples
- API

## Fase 3 — Persistencia básica

Objetivo:

- guardar jobs y resultados de forma más explícita

Resultado esperado:

- entrada de jobs desde archivo
- salida de resultados por job
- trazabilidad entre job, cliente e intento

Persistencia inicial razonable:

- JSON o archivos locales

No hace falta base de datos todavía.

## Fase 4 — Integración externa

Objetivo:

- permitir que otro sistema cree jobs o reciba resultados

Posibles caminos:

- carpeta de entrada vigilada
- CLI más estructurada
- API simple

Esta fase debe venir después de estabilizar el runner local.

## Fase 5 — Dashboard

Objetivo:

- visibilidad operativa y seguimiento

Contenido posible:

- jobs
- estados
- clientes completados/fallidos
- tiempos
- enlaces a evidencias

Debe llegar al final, no al principio.

## 8. Qué NO hacer todavía

- No construir un dashboard ahora.
- No construir una API compleja ahora.
- No añadir paralelismo entre clientes.
- No ejecutar múltiples workers contra la misma sesión de escritorio.
- No crear una arquitectura enterprise con demasiadas capas.
- No introducir colas distribuidas, brokers o microservicios.
- No intentar generalizar demasiado antes de tener al menos dos sedes reales.
- No reescribir RedTrust ni el flujo de Edge solo por “limpieza”.

## 9. Riesgos

Los principales riesgos siguen siendo los mismos que en el sistema actual.

### UI Automation

- RedTrust depende de una UI real de Windows.
- Cambios visuales o de controles pueden romper la automatización.
- La estabilidad depende de foco, tiempos y sesión interactiva.

### Popup de certificado

- El popup es una zona frágil por naturaleza.
- Puede no aparecer, aparecer tarde o comportarse distinto según el certificado o el entorno.
- La detección y automatización del popup seguirá siendo un riesgo transversal.

### Edge y foco de ventana

- El navegador puede arrancar sin quedar realmente en foreground.
- El foco nativo depende de Windows y del comportamiento de Edge.
- Esto afecta a la visibilidad del popup y a la continuidad del flujo.

### RedTrust

- La preselección del certificado ocurre fuera de Playwright.
- Es un punto crítico previo al login web.
- Cualquier generalización futura debe tratar RedTrust como integración sensible y compartida.

## 10. Decisiones abiertas

Estas decisiones conviene dejarlas explícitas antes de implementar la plataforma:

- Cómo llegará el input:
  - `clientes.json`
  - jobs JSON
  - carpeta de entrada
  - API

- Cómo se identificarán los jobs:
  - timestamp
  - UUID
  - combinación de sede + fecha + secuencia

- Qué volumen real se espera:
  - pocos jobs manuales al día
  - procesamiento continuo
  - lotes grandes

- Cuántos workers habrá:
  - uno local
  - uno por máquina
  - varios en el futuro

- Qué sedes siguientes son realmente prioritarias:
  - `dgt`
  - otras

- Qué partes del resultado deben estandarizarse entre sedes y cuáles seguirán siendo específicas.

- Qué nivel de persistencia se necesita realmente:
  - solo archivos
  - base de datos ligera
  - integración externa posterior

## Resumen operativo

La evolución recomendada no es rehacer el proyecto, sino convertir el sistema actual en:

- un `core` pequeño y estable
- una integración compartida de certificados y navegador
- una primera sede `dehu`
- futuras sedes añadidas como módulos paralelos

El orden correcto es:

1. aislar DEHú como primera sede
2. introducir el concepto de job
3. añadir persistencia básica
4. abrir integración externa
5. dejar dashboard y capas adicionales para el final
