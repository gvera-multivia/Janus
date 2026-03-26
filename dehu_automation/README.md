# Automatización de Altas en DEHú

## 1. Descripción general

Este proyecto automatiza el alta de destinatarios en DEHú (Dirección Electrónica Habilitada única) a partir de una lista de clientes en JSON.

El flujo actual combina:

- Automatización de escritorio en Windows para preseleccionar certificados con RedTrust.
- Lanzamiento de Microsoft Edge con remote debugging.
- Automatización web con Playwright Sync API sobre DEHú.
- Registro estructurado de resultados en JSON, incluyendo tiempos, fase de error y evidencias.

El sistema está diseñado para procesar clientes de forma secuencial, registrar el resultado individual de cada uno y, al finalizar la primera pasada, ejecutar una segunda pasada única solo sobre ciertos errores reintentables.

Actualmente admite dos formas de ejecución local:

- modo legacy, leyendo `clientes.json`
- modo job local, leyendo un archivo JSON con `job_id`, `sede` y `clientes`

## 2. Flujo paso a paso

### Flujo completo por cliente

1. Se carga la lista de clientes:
   - desde `clientes.json` en modo legacy
   - o desde un `job.json` local si se pasa como argumento
2. Se valida que cada entrada tenga:
   - `nif`
   - `email` con formato válido
   - `id_redtrust`
3. Si la entrada es inválida, se registra `error_datos_entrada` y no se procesa más ese cliente.
4. Si `RUN_REDTRUST = True`, se lanza la preselección del certificado en RedTrust mediante un subproceso que ejecuta `redtrust_window_inspect.py`.
5. Si RedTrust falla, se registra `error_redtrust`.
6. Si RedTrust va bien, se lanza Edge:
   - se cierran procesos `msedge.exe` existentes
   - se crea un perfil temporal por NIF en `C:\temp\edge_profile_<nif>`
   - se arranca Edge con remote debugging en el puerto `9222`
   - se intenta localizar y enfocar una ventana nativa visible de Edge
   - Playwright se conecta mediante CDP (`connect_over_cdp`)
7. Se navega a DEHú y se pulsa:
   - `Acceder a DEHu`
   - `Acceso DNIe / Certificado`
8. Si `AUTO_CONFIRM_CERTIFICATE_POPUP = True`, se espera el popup nativo del certificado:
   - si se detecta y confirma, el flujo continúa
   - si DEHú muestra el modal funcional de certificado no enviado, se registra `error_certificado_invalido`
   - si no aparece popup válido ni modal funcional dentro del timeout, se registra `popup_no_detectado`
9. Se valida el login buscando una página autenticada o señales de navegación correcta en DEHú.
10. Si el login no se valida, se registra `error_login`.
11. Si el login es correcto, se accede a `Datos de contacto` y se intenta dar de alta el correo del cliente.
12. El alta puede terminar como:
   - `alta_realizada`
   - `cliente_ya_dado_de_alta`
   - `error_alta`
13. Después se intenta cerrar sesión en DEHú.
14. Si el logout falla, se registra `error_logout`.
15. El resultado final del cliente se guarda en `resultados_clientes.json`.

## 3. Arquitectura actual

### Archivos principales

- [`main.py`](/c:/Users/Daniel%20Gonzalez/dehu_automation/main.py)
  Punto de entrada del sistema. Carga clientes, ejecuta la pasada 1 y la pasada 2 de reintento, guarda resultados y muestra el resumen final.

- [`core/runner.py`](/c:/Users/Daniel%20Gonzalez/dehu_automation/core/runner.py)
  Núcleo común mínimo de ejecución por lote:
  - validación de datos de entrada
  - construcción del modelo `Cliente`
  - ejecución secuencial por cliente
  - construcción de entradas de resultado por intento

- [`core/job.py`](/c:/Users/Daniel%20Gonzalez/dehu_automation/core/job.py)
  Soporte mínimo de jobs locales:
  - carga de un job desde JSON
  - construcción de un job local legacy a partir de `clientes.json`

- [`core/results.py`](/c:/Users/Daniel%20Gonzalez/dehu_automation/core/results.py)
  Helpers compartidos de resultados y evidencias:
  - `build_process_result`
  - `build_result_entry`
  - `capture_web_evidence`

- [`sites/dehu/site.py`](/c:/Users/Daniel%20Gonzalez/dehu_automation/sites/dehu/site.py)
  Encapsula el flujo funcional específico de DEHÚ como primera sede:
  - RedTrust
  - Edge
  - login con certificado
  - alta
  - logout

- [`sites/registry.py`](/c:/Users/Daniel%20Gonzalez/dehu_automation/sites/registry.py)
  Registro mínimo de sedes soportadas. Actualmente resuelve `dehu`.

- [`dehu/dehu_automation.py`](/c:/Users/Daniel%20Gonzalez/dehu_automation/dehu/dehu_automation.py)
  Lógica web de DEHú con Playwright:
  - navegación al portal
  - inicio de login con certificado
  - espera y confirmación del popup nativo
  - detección del modal funcional de error de certificado
  - validación del login
  - alta de destinatario
  - cierre de sesión

- [`browser/edge_browser.py`](/c:/Users/Daniel%20Gonzalez/dehu_automation/browser/edge_browser.py)
  Arranque de Edge con remote debugging, espera del puerto CDP, intento de foco de ventana nativa y conexión Playwright.

- [`certificates/redtrust_bridge.py`](/c:/Users/Daniel%20Gonzalez/dehu_automation/certificates/redtrust_bridge.py)
  Puente entre `main.py` y RedTrust. Ejecuta `redtrust_window_inspect.py` como subproceso y devuelve `True/False`.

- [`redtrust_window_inspect.py`](/c:/Users/Daniel%20Gonzalez/dehu_automation/redtrust_window_inspect.py)
  Automatización de escritorio sobre RedTrust con `pywinauto` y `pyautogui`:
  - localización del icono en bandeja
  - apertura del menú de certificados
  - detección de la ventana real de RedTrust Agent
  - búsqueda por `id_redtrust`
  - selección del certificado
  - confirmación final

- [`models/cliente.py`](/c:/Users/Daniel%20Gonzalez/dehu_automation/models/cliente.py)
  Modelo simple de cliente (`nif`, `nombre`, `email`, `id_redtrust`).

- [`utils/logger.py`](/c:/Users/Daniel%20Gonzalez/dehu_automation/utils/logger.py)
  Logger común del proyecto. Actualmente escribe a consola mediante `logging.StreamHandler`.

### Comunicación entre módulos

1. `main.py` carga un job local:
   - desde `clientes.json` en modo legacy
   - o desde un `job.json` pasado como argumento
2. `main.py` resuelve la sede mediante `sites/registry.py`.
3. `main.py` delega la ejecución por lote en `core/runner.py`.
4. `core/runner.py` valida cada entrada, construye `Cliente` y delega el flujo funcional en la sede correspondiente.
5. `sites/dehu/site.py` invoca `select_certificate(...)` del bridge.
6. El bridge lanza `redtrust_window_inspect.py`.
7. `sites/dehu/site.py` invoca `start_browser(...)` para arrancar Edge y conectar Playwright.
8. `sites/dehu/site.py` llama a `dehu/dehu_automation.py` para el flujo web.
9. `core/results.py` construye la salida estructurada y captura evidencias.
10. `main.py` guarda `resultados_clientes.json` y muestra el resumen.

## 4. Formato de entrada

El sistema admite actualmente dos formatos de entrada.

### A. Modo legacy: `clientes.json`

Debe ser una lista JSON de objetos. Cada objeto representa un cliente.

Ejemplo:

```json
[
  {
    "nif": "12345678A",
    "nombre": "Maria Louders",
    "email": "lourdes@email.com",
    "id_redtrust": "43534 -"
  }
]
```

### Campos utilizados

- `nif`: obligatorio
- `nombre`: se conserva en resultados, pero no se valida para permitir o bloquear el procesamiento
- `email`: obligatorio y debe cumplir una validación básica de email
- `id_redtrust`: obligatorio; se usa para buscar/preseleccionar el certificado en RedTrust

Si falta `nif`, falta `id_redtrust` o el `email` no pasa la validación, el cliente se registra como `error_datos_entrada`.

### B. Modo job local: `job.json`

También puede ejecutarse pasando un archivo de job a `main.py`.

Estructura mínima esperada:

```json
{
  "job_id": "job_2026-03-26_001",
  "sede": "dehu",
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

Campos del job:

- `job_id`: obligatorio
- `sede`: obligatorio
- `clientes`: obligatorio, debe ser una lista

## 5. Formato de salida

El sistema guarda los resultados en `resultados_clientes.json`.

Cada entrada contiene:

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

### Significado de algunos campos

- `intento`: número de pasada. `1` para ejecución inicial, `2` para reintento.
- `job_id`: identificador del job local que originó la ejecución.
- `sede`: sede procesada para esa entrada.
- `resultado`: estado final del cliente.
- `mensaje`: descripción resumida del resultado.
- `fase_error`: fase funcional donde se produjo el error, cuando aplica.
- `url_error`: URL capturada desde Playwright en caso de error.
- `captura_error`: ruta de screenshot si fue posible generar evidencia.

## 6. Tipos de resultado

Los valores de `resultado` que devuelve actualmente el flujo son:

- `alta_realizada`
  El correo se ha dado de alta correctamente.

- `cliente_ya_dado_de_alta`
  El sistema interpreta que el cliente ya tiene el correo configurado.

- `error_datos_entrada`
  La entrada del cliente no tiene estructura válida o faltan datos obligatorios.

- `error_redtrust`
  Falló la preselección del certificado en RedTrust.

- `error_edge`
  Falló el arranque de Edge o la conexión de Playwright al navegador.

- `error_certificado_invalido`
  Tras intentar el login con certificado, DEHú mostró el modal funcional de certificado no enviado o no usable.

- `popup_no_detectado`
  No se detectó o no se automatizó un popup válido de certificado dentro del timeout.

- `error_login`
  No se pudo validar el acceso autenticado a DEHú.

- `error_logout`
  El flujo llegó al final, pero no pudo cerrar sesión correctamente.

- `error_alta`
  Falló el proceso de alta del destinatario.

- `error_inesperado`
  Excepción no controlada durante el procesamiento del cliente.

## 7. Sistema de reintentos

El sistema actual hace una segunda pasada automática al terminar la primera ejecución completa.

### Cómo funciona

1. `main.py` procesa todos los clientes una vez.
2. Al terminar, revisa los `resultado` de esa primera pasada.
3. Selecciona solo los clientes cuyo resultado esté en `RETRYABLE_RESULTS`.
4. Ejecuta una segunda pasada única solo para esos clientes.
5. No sobrescribe el resultado anterior: añade una nueva entrada al JSON con `intento = 2`.

### Resultados que se reintentan actualmente

En el estado actual del código:

- `error_edge`
- `error_login`
- `error_inesperado`
- `error_logout`

### Importante

El resumen final (`print_summary`) cuenta entradas del JSON, no clientes únicos. Por tanto, si hay reintentos, el total final incluye tanto `intento = 1` como `intento = 2`.

## 8. Dependencias técnicas

### Tecnologías principales

- Python
- Playwright Sync API
- Microsoft Edge con remote debugging por CDP
- `pywinauto` para automatización de ventanas de Windows
- `pyautogui` para algunos fallbacks de click
- `requests` para comprobar que el puerto de debugging de Edge está listo

### Dependencias observables en el código

- `playwright.sync_api`
- `pywinauto`
- `pywinauto.keyboard`
- `pyautogui`
- `requests`
- `logging`

### Entorno operativo esperado

- Windows
- Sesión de escritorio interactiva disponible
- Microsoft Edge instalado en:
  `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`
- RedTrust instalado y accesible desde rutas conocidas o variables de entorno

## 9. Logging y evidencias

### Logging

El proyecto utiliza un logger común (`dehu`) definido en [`utils/logger.py`](/c:/Users/Daniel%20Gonzalez/dehu_automation/utils/logger.py).

Características actuales:

- salida a consola
- nivel `INFO`
- formato:
  `%(asctime)s | %(levelname)s | %(message)s`

### Evidencias

Cuando se produce un error en una fase web, `main.py` intenta guardar:

- `url_error`: URL actual de la página
- `captura_error`: screenshot en `artifacts/errores/`

El nombre del fichero de captura sigue el patrón:

```text
<nif>_<timestamp>_<fase_error>.png
```

Ejemplo:

```text
artifacts\errores\19865678C_2026-03-25T13-21-02_popup_certificado.png
```

## 10. Limitaciones actuales

Estas limitaciones están basadas en el código actual, no en propuestas de mejora.

- Dependencia fuerte de Windows y de una sesión gráfica real
  RedTrust y parte del manejo del popup dependen de UI Automation y foco de ventanas.

- Dependencia de la UI de terceros
  La automatización depende de textos, controles y comportamiento visual de:
  - RedTrust
  - Edge
  - DEHú
  - Cl@ve

- El popup de certificado sigue siendo una zona sensible
  Aunque hay filtros y comprobaciones adicionales, la detección del popup depende de inspección de ventanas nativas y controles UIA.

- El foco de Edge es best-effort
  `browser/edge_browser.py` intenta localizar una ventana visible de Edge, restaurarla, maximizarla y enfocarla, pero esto sigue dependiendo del comportamiento de Windows y del navegador.

- El arranque de Edge cierra procesos existentes
  Antes de iniciar Edge, `start_browser()` ejecuta `taskkill /f /im msedge.exe`.

- Uso de timeouts y esperas fijas
  Hay `time.sleep`, `wait_for_timeout` y esperas por sondeo tanto en UIA como en Playwright. El comportamiento temporal depende del estado real del escritorio y de la web.

- El logout puede fallar aunque el alta ya se haya realizado
  El resultado final del cliente puede terminar siendo `error_logout` aunque la parte funcional anterior haya progresado correctamente.

- El resumen final no distingue clientes únicos de intentos
  Si hubo reintentos, el total mostrado en logs no representa necesariamente el número de clientes distintos.

## 11. Cómo ejecutar el proyecto

### Requisitos básicos

- Windows con sesión de escritorio desbloqueada
- Python instalado
- Dependencias del proyecto instaladas
- Microsoft Edge instalado en la ruta esperada
- RedTrust instalado y operativo
- Certificados disponibles en RedTrust

### Archivos esperados

- `clientes.json` en la raíz del proyecto para modo legacy
- o un `job.json` local para modo job

### Ejecución principal

Desde la raíz del proyecto:

```powershell
python main.py
```

O bien:

```powershell
python main.py <job.json>
```

### Qué hace esa ejecución

- carga `clientes.json` o un `job.json`
- procesa todos los clientes en una primera pasada
- hace una segunda pasada solo para ciertos resultados reintentables
- guarda `resultados_clientes.json`
- escribe logs en consola

### Ejecución manual de RedTrust

El script de RedTrust también puede ejecutarse directamente:

```powershell
python redtrust_window_inspect.py search <valor>
python redtrust_window_inspect.py diagnose
python redtrust_window_inspect.py full <valor>
```

Y el bridge de certificados lo invoca internamente con:

- `search`
- `diagnose`
- `full`

En el flujo principal actual se usa `mode="full"`.
