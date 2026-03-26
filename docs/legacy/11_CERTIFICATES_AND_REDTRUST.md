# Certificados y RedTrust

## Papel en el sistema

Sin certificados válidos y sin automatización GUI estable, la plataforma no funciona. Este subsistema es transversal a casi todos los robots.

## Piezas principales

### `app/redtrust/redtrust_manager.py`

Responsabilidades:

- localizar el icono de RedTrust en la bandeja del sistema
- abrir el agente
- hacer login con `USUARIO` y `PASSWORD`
- seleccionar uno o varios certificados

### `app/robot/handle_certificate.py`

Responsabilidades:

- detectar la ventana nativa del portal correspondiente
- localizar el selector “Seleccionar un certificado”
- elegir el certificado por `recipient_name`
- aceptar o cancelar la operación

## Modelo operativo

Hay dos pasos separados:

1. Cargar el certificado correcto en RedTrust.
2. Atender el popup del portal que pide ese certificado.

Por eso los robots suelen lanzar en paralelo:

- un proceso de portal
- un proceso de manejo de certificado

## Sedes y ventanas conocidas

`CertificateManager` mantiene un diccionario `SITES` con sedes como:

- Andalucía
- Asturias
- ATC
- Badajoz
- Baleares
- Burgos
- Castilla-La Mancha
- Castilla y León
- Ceuta
- Comunidad Valenciana
- La Rioja
- Madrid
- Melilla
- País Vasco
- eNotum
- Mahón
- DEV/DGT
- Dehú
- Terrassa
- Xaloc
- Migjorn Gran
- Ayuntamiento de Málaga
- Seu Judicial Gencat

## Fragilidad principal

- depende de títulos de ventana exactos
- depende del idioma del portal
- depende de que el escritorio del worker esté operativo
- depende del focus y timings de ventana
