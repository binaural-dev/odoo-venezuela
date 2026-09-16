# l10n_ve_auditlog_base

## Purpose

Base de auditoría técnica de la localización: extiende el módulo OCA `auditlog` para registrar también las peticiones HTTP salientes de Odoo (llamadas a APIs externas como BCV, Tesote, Megasoft), parcheando `requests.Session.request` al importar `models/requests_monitor.py`. Agrega campos de request saliente a `auditlog.http.request`, la configuración por compañía del nivel de logging, y un menú raíz "Auditoría" que agrupa las vistas de `auditlog`. Depende de `auditlog` y `l10n_ve_base`, y se instala automáticamente (`auto_install`).

## Requirements

### Requirement: Registro automático de fallos en peticiones salientes

Cuando una petición saliente hecha con `requests` lanza `RequestException`, el parche de `Session.request` DEBE (MUST) registrar primero el fallo como `error` en el log del servidor (con traceback) y después crear —sin `sudo()`, con el usuario de la petición en curso— un registro en `auditlog.http.request` con `is_outgoing = True`, `name` = URL, `http_method` en mayúsculas, `request_url`, `error_type` (nombre de la clase de la excepción), `error_message`, `error_traceback`, `request_body` (el `data` o el `json` del kwargs convertido a texto), `user_id`, y `response_status` (que queda vacío si la excepción no trae respuesta); si la excepción trae respuesta también guarda `response_body` y `response_headers`. Acto seguido DEBE (MUST) relanzar la excepción original. Si no hay contexto de request de Odoo disponible, el fallo solo se registra en el log del servidor.

#### Scenario: API externa caída

- **WHEN** una llamada saliente a un servicio externo falla por timeout o error de conexión dentro de una petición de Odoo
- **THEN** se crea un registro de auditoría marcado como saliente con el tipo y mensaje del error, y la excepción se propaga al código que hizo la llamada

#### Scenario: Fallo fuera de una petición de Odoo

- **WHEN** la llamada saliente falla sin contexto de request de Odoo (por ejemplo desde un cron o un script sin request)
- **THEN** no se crea registro de auditoría y el evento queda solo en el log del servidor

### Requirement: Registro de peticiones exitosas solo en modo "all"

El parche DEBE (MUST) registrar las peticiones salientes exitosas —creando el registro con `sudo()`, con método, URL, `response_status`, `request_body`, `response_body` y `response_headers`— únicamente cuando `_should_log_all()` es verdadero, es decir cuando hay contexto de request y el campo `log_outgoing_requests` de `request.env.company` vale `all`; con el valor por defecto `errors_only`, o si no hay contexto de request, solo se registran los fallos.

#### Scenario: Modo solo errores

- **WHEN** la compañía tiene `log_outgoing_requests = errors_only` y una petición saliente responde correctamente
- **THEN** no se crea ningún registro de auditoría

#### Scenario: Modo completo

- **WHEN** la compañía tiene `log_outgoing_requests = all` y una petición saliente responde correctamente
- **THEN** se crea un registro saliente con método, URL, estado, cuerpo y cabeceras de la respuesta

### Requirement: Truncado configurable de los cuerpos registrados

El sistema DEBE (MUST) truncar `request_body` y `response_body` a los primeros `response_body_max_chars` caracteres configurados en `request.env.company`; con el valor por defecto `0` los cuerpos se guardan completos. El truncado no se aplica a `error_message`, `error_traceback` ni `response_headers`.

#### Scenario: Límite configurado

- **WHEN** la compañía tiene `response_body_max_chars = 500` y se registra una petición con una respuesta más larga
- **THEN** el registro guarda solo los primeros 500 caracteres del cuerpo de la respuesta y del cuerpo enviado

### Requirement: El logging nunca interrumpe la petición original

Cualquier error interno al crear el registro de auditoría (en `_log_failure` o `_log_success`) DEBE (MUST) capturarse y limitarse a un warning en el log del servidor, sin alterar el resultado de la petición saliente; `_should_log_all` también absorbe cualquier excepción y devuelve `False`.

#### Scenario: Error al persistir el log

- **WHEN** la creación del registro de auditoría falla (por ejemplo porque el usuario de la petición no tiene permiso de creación sobre `auditlog.http.request`, que en la ruta de fallo no usa `sudo()`)
- **THEN** la petición saliente conserva su respuesta (o su excepción original) y el fallo del log solo aparece como warning

### Requirement: Configuración del monitoreo por compañía

Los campos `log_outgoing_requests` (selección `errors_only` "Log Only Failed Requests" / `all` "Log All Outgoing Requests", por defecto `errors_only`) y `response_body_max_chars` (Integer, por defecto `0`) DEBEN (MUST) definirse en `res.company` y exponerse en `res.config.settings` como campos related con `readonly=False`.

#### Scenario: Activar el registro completo

- **WHEN** un administrador cambia el logging saliente a "Log All Outgoing Requests" en ajustes y guarda
- **THEN** `log_outgoing_requests` de la compañía queda en `all`

### Requirement: Menú de Auditoría para el grupo de auditores

El módulo DEBE (MUST) exponer un menú raíz "Auditoría" (`menu_auditoria_root`) visible solo para el grupo `auditlog.group_auditlog_user`, con los submenús Logs, Log Lines, HTTP Requests, User Sessions y Rules apuntando a las acciones de `auditlog`, y DEBE (MUST) reasignar el menú original `auditlog.menu_audit` bajo `base.menu_custom`. Las vistas heredadas de `auditlog.http.request` (formulario, lista y búsqueda) DEBEN (MUST) mostrar los campos de peticiones salientes —el grupo "Outgoing Request" del formulario solo es visible cuando `is_outgoing`— y ofrecer los filtros "Outgoing Requests" y "Failed Requests" más los agrupamientos por tipo de error y por método HTTP.

#### Scenario: Usuario sin grupo de auditoría

- **WHEN** un usuario que no pertenece a `auditlog.group_auditlog_user` navega el sistema
- **THEN** el menú "Auditoría" no le aparece

#### Scenario: Filtrar peticiones fallidas

- **WHEN** un auditor aplica el filtro "Failed Requests" en HTTP Requests
- **THEN** solo se listan registros con `is_outgoing = True` y `error_type` establecido
