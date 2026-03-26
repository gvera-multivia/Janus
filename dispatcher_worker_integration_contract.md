# Contrato de Integracion Dispatcher <-> Worker

Estado: borrador de alineacion previa a implementacion

## 1. Proposito del contrato

Este documento define el contrato minimo de integracion entre:

- el **Dispatcher**, como plano de control del sistema
- el **Worker de automatizacion** de este repositorio, como executor de jobs

Su objetivo es resolver la frontera entre ambos sistemas sin redisenar la automatizacion sensible ya existente.

Problemas que resuelve:

- deja claro quien orquesta y quien ejecuta
- fija la unidad de trabajo compartida
- define el payload minimo que debe recibir el worker
- define que estados, senales y artefactos deben ser visibles para el dispatcher
- evita que el worker absorba responsabilidades que pertenecen al dispatcher

Este contrato no redefine:

- RedTrust
- Edge
- popup
- login
- alta
- logout

Tampoco introduce:

- cola local del worker
- dashboard propio del worker
- scheduling propio del worker

## 2. Reparto de responsabilidades

### Dispatcher

El dispatcher es responsable de:

- descubrimiento de trabajo
- consulta y agrupacion previa de items de negocio
- encolado
- priorizacion
- asignacion a workers
- control de ejecucion a nivel global
- dashboard global
- requeue y recovery a nivel task/job cuando aplique
- conocimiento de disponibilidad de workers

El dispatcher es el **control plane**.

### Worker

El worker es responsable de:

- recibir un job/task ya asignado
- validar que le corresponde ejecutarlo
- ejecutar el job sobre la sede indicada
- aplicar su politica interna de reintentos dentro del job
- generar artefactos locales por job
- publicar estado minimo de ejecucion
- publicar resultado final del job

El worker es el **execution plane**.

### Fuera de alcance del worker

El worker no debe gestionar:

- cola propia
- dashboard propio
- priorizacion global
- scheduling global
- descubrimiento de trabajo
- logica SQL de seleccion de items

## 3. Unidad de trabajo

La unidad de trabajo compartida sera:

- **1 task del dispatcher = 1 job del worker**

Consecuencia practica:

- el dispatcher asigna una unica task
- el worker la ejecuta como un job completo
- el job produce un unico conjunto de artefactos en `outputs/jobs/<job_id>/`

### Recomendacion sobre `task_id` y `job_id`

Recomendacion para v1:

- el payload debe incluir **ambos campos**: `task_id` y `job_id`
- ambos campos deben tener **el mismo valor**

Motivo:

- el dispatcher ya trabaja naturalmente con `task_id`
- el worker ya trabaja naturalmente con `job_id`
- mantener ambos y hacerlos equivalentes reduce traducciones, ambiguedad y errores de correlacion
- preserva trazabilidad clara en Redis, logs, outputs y dashboard

Regla recomendada:

- `task_id == job_id` en v1

Si en el futuro hace falta diferenciar la identidad del job de una identidad de transporte o de reintento, se recomienda anadir un tercer campo:

- `dispatch_id` o `attempt_id`

No se recomienda separar `task_id` y `job_id` desde el inicio.

## 4. Contrato de entrada al worker

### Payload minimo recomendado

| Campo | Req. | Tipo | Descripcion |
| --- | --- | --- | --- |
| `task_name` | Si | string | Nombre tecnico de la tarea publicada por el dispatcher. Recomendado: `run_sede_job`. |
| `task_id` | Si | string | Identificador unico de la task en el dispatcher. |
| `job_id` | Si | string | Identificador unico del job en el worker. En v1 debe ser igual a `task_id`. |
| `sede` | Si | string | Sede a ejecutar. Ejemplo: `dehu`. |
| `clientes` | Si | array | Lista de clientes a procesar por el job. |
| `source` | No | string | Origen funcional del job. Ejemplo: `dispatcher`, `scheduler`, `api_manual`. |
| `metadata` | No | object | Metadatos adicionales de trazabilidad o negocio. |

### Contrato minimo por cliente

Para el worker actual, cada cliente debe llegar ya materializado con estos campos:

| Campo | Req. | Tipo | Descripcion |
| --- | --- | --- | --- |
| `nif` | Si | string | Identificador del cliente. |
| `nombre` | Si | string | Nombre visible del cliente. |
| `email` | Si | string | Email a usar en el flujo actual. |
| `id_redtrust` | Si | string | Identificador/selector del certificado en RedTrust. |

Reglas:

- el worker puede ignorar campos extra no reconocidos
- el dispatcher no debe enviar solo IDs de negocio si el worker no tiene capa propia de resolucion
- el payload debe ser autocontenido para ejecucion

### Ejemplo JSON

```json
{
  "task_name": "run_sede_job",
  "task_id": "job_2026_03_26_001",
  "job_id": "job_2026_03_26_001",
  "sede": "dehu",
  "source": "dispatcher",
  "metadata": {
    "requested_by": "scheduler",
    "priority": "normal",
    "batch_reason": "altas_pendientes"
  },
  "clientes": [
    {
      "nif": "12345678A",
      "nombre": "Maria Louders",
      "email": "lourdes@email.com",
      "id_redtrust": "43534 -"
    }
  ]
}
```

## 5. Capacidades del worker

El dispatcher no debe tratar este worker como un executor generico. Debe conocer o poder inferir sus capacidades minimas.

### Capacidades estaticas recomendadas

| Campo | Valor recomendado |
| --- | --- |
| `supported_sites` | `["dehu"]` |
| `max_concurrency` | `1` |
| `interactive_desktop_required` | `true` |
| `execution_mode` | `single_slot_interactive` |
| `os` | `windows` |
| `edge_required` | `true` |
| `redtrust_required` | `true` |
| `artifacts_supported` | `["input.json", "results.json", "summary.json"]` |

### Capacidades dinamicas recomendadas

El heartbeat o estado runtime del worker deberia incluir como minimo:

- `worker_id`
- `status`
- `timestamp`
- `current_task`
- `cpu_percent`
- `memory_percent`

### Ejemplo de declaracion

```json
{
  "worker_id": "host01@HOST01",
  "supported_sites": ["dehu"],
  "max_concurrency": 1,
  "interactive_desktop_required": true,
  "execution_mode": "single_slot_interactive",
  "os": "windows",
  "edge_required": true,
  "redtrust_required": true,
  "artifacts_supported": ["input.json", "results.json", "summary.json"],
  "status": "free",
  "current_task": null,
  "cpu_percent": 12.4,
  "memory_percent": 43.1,
  "timestamp": "2026-03-26T12:00:00"
}
```

## 6. Estados y ciclo de vida

### Estados minimos del job

| Estado | Significado | Imprescindible ahora |
| --- | --- | --- |
| `pending` | Task creada o asignada pero no iniciada en el worker. | Si |
| `running` | Job aceptado e iniciado por el worker. | Si |
| `completed` | Job terminado con exito global. | Si |
| `completed_with_errors` | Job terminado con artefactos validos, pero con errores de cliente o datos. | Si |
| `failed` | Fallo tecnico o de ejecucion que impide considerar el job terminado correctamente. | Si |
| `cancelled` | Cancelacion explicita. | No, mas adelante |

### Semantica recomendada

- `completed` significa que el job llego al final y no hubo errores finales por cliente.
- `completed_with_errors` significa que el job llego al final y genero artefactos validos, pero al menos un cliente quedo con error o datos de entrada invalidos.
- `failed` significa fallo de nivel job o fallo tecnico grave. Puede no haber artefactos completos o puede existir solo evidencia parcial.

### Estados minimos de disponibilidad del worker

| Estado | Significado | Imprescindible ahora |
| --- | --- | --- |
| `free` | Disponible para recibir una task. | Si |
| `busy` | Ejecutando una task/job. | Si |
| `offline` | Sin heartbeat valido o no operativo. | Si |

### Ciclo de vida minimo esperado

```text
Dispatcher:
pending -> assigned

Worker/job:
running -> completed | completed_with_errors | failed

Worker availability:
free -> busy -> free
free/busy -> offline si expira el heartbeat
```

### Nota sobre reintentos

En este worker, los reintentos internos siguen siendo responsabilidad del propio worker y forman parte del job.

Regla recomendada:

- el dispatcher no debe reinterpretar `completed_with_errors` como motivo automatico para relanzar el mismo job
- los reintentos globales del dispatcher deben reservarse para fallos de asignacion, perdida de worker o fallos job-level sin cierre limpio

## 7. Eventos o senales minimas de ejecucion

El dispatcher necesita conocer, como minimo, estas senales:

| Senal | Momento | Payload minimo |
| --- | --- | --- |
| `heartbeat` | Periodico | `worker_id`, `status`, `timestamp`, `current_task` |
| `job_started` | Al comenzar el job | `worker_id`, `task_id`, `job_id`, `sede`, `timestamp` |
| `job_finished` | Al terminar el job | `worker_id`, `task_id`, `job_id`, `estado_job`, `timestamp` |
| `job_failed` | En fallo grave o terminal | `worker_id`, `task_id`, `job_id`, `error`, `timestamp` |
| `availability_changed` | Cambio `free` <-> `busy` | `worker_id`, `status`, `current_task`, `timestamp` |

### Senales imprescindibles ahora

- heartbeat
- inicio de job
- fin de job
- cambio de disponibilidad

### Senales recomendables mas adelante

- progreso intermedio por job
- progreso por cliente
- cancelacion cooperativa
- razones detalladas de retry tecnico

No es necesario fijar en este documento si estas senales viajaran por Redis directo, wrapper o callback. Ese punto queda como decision abierta.

## 8. Artefactos de salida

El worker debe seguir produciendo estos artefactos por job:

- `input.json`
- `results.json`
- `summary.json`

Ruta esperada:

```text
outputs/jobs/<job_id>/
```

### Significado de cada artefacto

#### `input.json`

Representa el snapshot del job ejecutado.

Debe contener como minimo:

- `job_id`
- `sede`
- `clientes`

Uso principal:

- auditoria
- reproducibilidad
- trazabilidad de entrada

#### `results.json`

Representa el detalle por cliente e intento.

Debe mantener estable, como minimo, el contrato actual de:

- `job_id`
- `sede`
- `nif`
- `nombre`
- `email`
- `id_redtrust`
- `intento`
- `resultado`
- `mensaje`
- `timestamp_inicio`
- `timestamp_fin`
- `duracion_segundos`
- `fase_error`
- `url_error`
- `captura_error`

Uso principal:

- analisis detallado del job
- diagnostico funcional
- trazabilidad por cliente

#### `summary.json`

Representa el cierre sintetico del job.

Debe ser el artefacto canonico para consumo rapido por parte del dispatcher o dashboard.

Contrato estable recomendado:

- `job_id`
- `sede`
- `estado_job`
- `total_clientes`
- `exitos`
- `errores`
- `errores_datos_entrada`
- `numero_reintentos`
- `duracion_total_aproximada`

Campos recomendados adicionales:

- `timestamp_inicio_job`
- `timestamp_fin_job`
- `source` u `origen`

### Artefacto canonico por caso de uso

- estado final del job: `summary.json`
- detalle funcional por cliente: `results.json`
- snapshot de entrada: `input.json`

### Regla de integracion

Para integracion, el dispatcher no debe depender de `resultados_clientes.json`.

Ese archivo debe considerarse:

- legacy
- local
- fuera del contrato estable dispatcher <-> worker

## 9. Suposiciones operativas

Este worker debe tratarse como:

- **single-slot interactivo**

Suposiciones obligatorias para el dispatcher:

- no soporta paralelismo real en la misma maquina
- no debe recibir mas de una task a la vez
- requiere sesion de escritorio interactiva
- depende de Windows
- depende de Edge
- depende de RedTrust
- depende de foco de UI y automatizacion de escritorio

Consecuencia operativa:

- `max_concurrency = 1` no es una preferencia, es una restriccion real del entorno
- el dispatcher no debe asignar una segunda task mientras el worker este en `busy`

## 10. Decisiones pendientes / abiertas

Antes de implementar, conviene cerrar estas decisiones:

- confirmar si en v1 `task_id == job_id` queda fijado como regla obligatoria
- decidir como se entrega el trabajo al worker:
  - wrapper/adapter local
  - CLI estructurada
  - API simple
  - consumidor de broker
- decidir como publica estado el worker:
  - Redis directo
  - wrapper que publique por el
  - callback hacia dispatcher
- decidir donde vive la logica de verificacion de asignacion:
  - dentro del worker
  - dentro de un wrapper del worker
- decidir como consumira el dispatcher los resultados:
  - leyendo `summary.json` y `results.json`
  - recibiendo una notificacion final con referencias
  - ambas cosas
- decidir si `input.json` debe materializarse al iniciar el job o solo al finalizar
- decidir que metadata adicional necesita el dispatcher en el payload:
  - prioridad
  - origen funcional
  - requested_by
  - correlacion externa
- decidir si el `task_name` de v1 sera unico y generico (`run_sede_job`) o uno por familia de robot

## 11. Recomendacion final

La implementacion minima recomendada despues de aprobar este contrato seria:

1. Crear un adapter fino de integracion que reciba el payload anterior y lo traduzca al job actual del worker.
2. Mantener `task_id == job_id` en v1.
3. Publicar heartbeat, `free/busy`, `job_started` y `job_finished`.
4. Mantener como artefactos oficiales `input.json`, `results.json` y `summary.json`.
5. Tratar este worker como `single-slot interactive` desde el primer dia.

No tocaria todavia:

- la logica sensible de automatizacion
- el flujo DEHU
- RedTrust
- Edge
- popup
- login
- alta
- logout
- paralelismo
- dashboard del worker
- cola del worker

Siguiente paso razonable tras aprobar el contrato:

- acordar el canal concreto de entrega y el canal concreto de publicacion de estado
- implementar un primer smoke test con un job sintetico `dehu`
- validar de extremo a extremo identidad, estados y artefactos antes de ampliar nada mas
