# l10n_ve_auditlog_base

## Purpose

Base de auditoría técnica de la localización: extiende el módulo OCA `auditlog` para registrar también las peticiones HTTP salientes de Odoo (llamadas a APIs externas como BCV, Tesote, Megasoft), parcheando `requests.Session.request` al cargar el módulo (`models/requests_monitor.py`). Agrega campos de request saliente a `auditlog.http.request`, la configuración por compañía del nivel de logging, y un menú raíz "Auditoría" que agrupa las vistas de `auditlog`. Depende de `auditlog` y `l10n_ve_base`, y se instala automáticamente (`auto_install`).

## Requirements

### Requirement: Registro automático de fallos en peticiones salientes

Cuando una petición saliente hecha con la librería `requests` lanza `RequestException`, el parche de `Session.request` DEBE (MUST) crear un registro en `auditlog.http.request` con `is_outgoing = True`, método HTTP, `request_url`, `error_type` (clase de la excepción), `error_message`, `error_traceback`, el cuerpo enviado, el usuario, y —si hubo respuesta— `response_status`, `response_body` y `response_headers`; luego DEBE (MUST) relanzar la excepción original. Si no hay contexto de request de Odoo disponible, el fallo solo se registra en el log del servidor.

#### Scenario: API externa caída

- **WHEN** una llamada saliente a un servicio externo falla por timeout o error de conexión dentro de una petición de Odoo
- **THEN** se crea un registro de auditoría marcado como saliente con el tipo y mensaje del error, y la excepción se propaga al código que hizo la llamada

#### Scenario: Fallo fuera de una petición de Odoo

- **WHEN** la llamada saliente falla sin contexto de request de Odoo (por ejemplo desde un proceso sin request)
- **THEN** no se crea registro de auditoría y el evento solo queda en el log del servidor

### Requirement: Registro de peticiones exitosas solo en modo "all"

El parche DEBE (MUST) registrar las peticiones salientes exitosas (con estado, cuerpos y cabeceras de la respuesta) únicamente cuando el campo `log_outgoing_requests` de la compañía vale `all`; con el valor por defecto `errors_only` solo se registran los fallos.

#### Scenario: Modo solo errores

- **WHEN** la compañía tiene `log_outgoing_requests = errors_only` y una petición saliente responde correctamente
- **THEN** no se crea ningún registro de auditoría

#### Scenario: Modo completo

- **WHEN** la compañía tiene `log_outgoing_requests = all` y una petición saliente responde correctamente
- **THEN** se crea un registro saliente con método, URL, estado y cuerpo de la respuesta

### Requirement: Truncado configurable de los cuerpos registrados

El sistema DEBE (MUST) truncar `request_body` y `response_body` a los primeros `response_body_max_chars` caracteres configurados en la compañía; con el valor por defecto `0` los cuerpos se guardan completos.

#### Scenario: Límite configurado

- **WHEN** la compañía tiene `response_body_max_chars = 500` y se registra una petición con una respuesta más larga
- **THEN** el registro guarda solo los primeros 500 caracteres del cuerpo

### Requirement: El logging nunca interrumpe la petición original

Cualquier error interno al crear el registro de auditoría (en `_log_failure` o `_log_success`) DEBE (MUST) capturarse y limitarse a un warning en el log del servidor, sin alterar el resultado de la petición saliente.

#### Scenario: Error al persistir el log

- **WHEN** la creación del registro de auditoría falla (por ejemplo por permisos o datos inválidos)
- **THEN** la petición saliente conserva su respuesta (o su excepción original) y el fallo del log solo aparece como warning

### Requirement: Configuración del monitoreo por compañía

Los campos `log_outgoing_requests` (selección `errors_only`/`all`, por defecto `errors_only`) y `response_body_max_chars` (por defecto `0`) DEBEN (MUST) definirse en `res.company` y ser editables desde los ajustes generales vía campos related con `readonly=False` en `res.config.settings`.

#### Scenario: Activar el registro completo

- **WHEN** un administrador cambia el logging saliente a "Log All Outgoing Requests" en ajustes y guarda
- **THEN** `log_outgoing_requests` de la compañía queda en `all`

### Requirement: Menú de Auditoría para el grupo de auditores

El módulo DEBE (MUST) exponer un menú raíz "Auditoría" visible solo para el grupo `auditlog.group_auditlog_user`, con submenús Logs, Log Lines, HTTP Requests, User Sessions y Rules apuntando a las acciones de `auditlog`, y la vista de `auditlog.http.request` DEBE (MUST) mostrar los campos de peticiones salientes con filtros "Outgoing Requests" y "Failed Requests".

#### Scenario: Usuario sin grupo de auditoría

- **WHEN** un usuario que no pertenece a `auditlog.group_auditlog_user` navega el sistema
- **THEN** el menú "Auditoría" no le aparece

#### Scenario: Filtrar peticiones fallidas

- **WHEN** un auditor aplica el filtro "Failed Requests" en HTTP Requests
- **THEN** solo se listan registros salientes con `error_type` establecido
