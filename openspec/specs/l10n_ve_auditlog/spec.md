# l10n_ve_auditlog

## Purpose

Consola de auditoría funcional sobre el tracking nativo del chatter: enriquece `mail.tracking.value` con el modelo y el autor del cambio, y expone menús de "Audit logs" filtrados a los documentos contables de la localización (`account.move`, `account.payment` y `account.retention`). Depende de `l10n_ve_accountant` y `l10n_ve_payment_extension` (que aporta el modelo `account.retention`). Es independiente de `l10n_ve_auditlog_base`, que audita a nivel técnico con el módulo OCA `auditlog`. El módulo declara el grupo `group_audit_report_seniat` ("Informe de auditoría Seniat"), que implica `account.group_account_readonly` (para alcanzar la cadena de menús de Contabilidad → Revisión), gatea sus propios menús "Audit logs"/"Audit logs lines", y reparenta bajo `account.account_logs_menu` los menús "Reglas" y "Registros" del módulo OCA `auditlog`, con acceso de solo lectura sobre `auditlog.log`, `auditlog.rule` y `auditlog.log.line`.

## Requirements

### Requirement: Modelo y autor en los valores de tracking

El modelo `mail.tracking.value` DEBE (MUST) contar con dos campos almacenados: `model` (Char, `_compute_model`, que copia `mail_message_id.model` y declara `@api.depends("mail_message_id")`) y `author_id` (Many2one a `res.partner`, `_compute_author`, que copia `mail_message_id.author_id` pero declara `@api.depends("author_id")`, es decir depende de sí mismo y no del mensaje). Por esa dependencia mal declarada, `author_id` se resuelve al crear la línea de tracking y no se recalcula si después cambia `mail_message_id`.

#### Scenario: Cambio rastreado en una factura

- **WHEN** un usuario modifica un campo con tracking de un documento y se genera el valor de seguimiento
- **THEN** la línea de tracking queda con el modelo del documento y el autor del mensaje asociado

#### Scenario: Reasignación del mensaje de una línea de tracking

- **WHEN** se cambia el `mail_message_id` de una línea de tracking ya existente
- **THEN** `model` se recalcula pero `author_id` conserva el autor anterior, porque su `depends` apunta al propio campo

### Requirement: Vista de logs de auditoría sobre documentos contables

La acción "Audit logs" (`l10n_ve_auditlog_action`) DEBE (MUST) abrir `mail.message` en modo `list,form` con el dominio `[('model', 'in', ('account.move','account.payment','account.retention'))]`, mostrando en la lista `author_id`, `model`, `subject`, `res_id` y `date`. La vista de búsqueda `l10n_ve_auditlog_search` (sobre `mail.message`) aporta los agrupamientos por modelo, por día y por autor; la acción no la referencia explícitamente con `search_view_id`.

#### Scenario: Consulta de auditoría

- **WHEN** un usuario abre el menú "Audit logs"
- **THEN** solo aparecen mensajes cuyo `model` es `account.move`, `account.payment` o `account.retention`

### Requirement: Vista de líneas de auditoría con valores anterior y nuevo

La acción "Audit logs lines" (`l10n_ve_mail_tracking_value_audits_action`) DEBE (MUST) abrir `mail.tracking.value` en modo `list,form` con el dominio `[('model', 'in', ('account.move','account.payment','account.retention'))]`, mostrando por línea `model`, `field_id`, `author_id`, `field_type` y los pares anterior/nuevo de cada tipo (`*_value_char`, `*_value_datetime`, `*_value_float`, `*_value_integer`, `*_value_text`). `field_type` es un campo `related="field_id.ttype"` agregado por el módulo; Odoo 19 fusionó el tracking monetario en `*_value_float` + `currency_id`, por lo que ya no existen `new_value_monetary`/`old_value_monetary`. La vista de búsqueda que acompaña al archivo (`l10n_ve_auditlog_lines_search`) está declarada sobre el modelo `mail.message`, no sobre `mail.tracking.value`, por lo que la lista de líneas no recibe esos filtros de agrupación.

#### Scenario: Revisión de un cambio de monto

- **WHEN** un auditor abre "Audit logs lines" tras un cambio en un campo monetario de un pago
- **THEN** la línea muestra el modelo, el campo, el autor y el valor flotante anterior y el nuevo

#### Scenario: Agrupar las líneas por autor

- **WHEN** el auditor busca en "Audit logs lines" los agrupamientos por modelo, día o autor
- **THEN** no están disponibles, porque la vista de búsqueda del módulo apunta a `mail.message`

### Requirement: Grupo de informe y visibilidad de los menús de auditoría

El módulo DEBE (MUST) declarar el grupo `group_audit_report_seniat` ("Informe de auditoría Seniat"), con `implied_ids` sobre `account.group_account_readonly`. Los menús "Audit logs" (`l10n_ve_auditlog_menu`) y "Audit logs lines" (`menu_l10n_ve_auditlogs_lines`) del propio módulo, y los menús "Reglas" (`auditlog.menu_action_auditlog_rule_tree`) y "Registros" (`auditlog.menu_audit_logs`) del módulo OCA `auditlog` —reparentados aquí bajo `account.account_logs_menu` (Contabilidad → Revisión → Registros)— DEBEN (MUST) llevar `groups="l10n_ve_auditlog.group_audit_report_seniat"` (o `group_ids` equivalente en los `ir.ui.menu` reparentados).

#### Scenario: Usuario con el permiso de informe ve los menús de auditoría

- **WHEN** un usuario pertenece a "Informe de auditoría Seniat"
- **THEN** ve los cuatro menús de auditoría bajo Contabilidad → Revisión → Registros, porque el grupo implica `account.group_account_readonly` y por tanto también la cadena de menús padre (Contabilidad, Revisión)

#### Scenario: Usuario sin el permiso no ve los menús de auditoría

- **WHEN** un usuario no pertenece a "Informe de auditoría Seniat" ni a ningún grupo que lo implique
- **THEN** no ve ninguno de los cuatro menús de auditoría, aunque tenga acceso a otras secciones de Contabilidad

### Requirement: Acceso de solo lectura sobre el log y las reglas de auditoría

El grupo `group_audit_report_seniat` DEBE (MUST) tener acceso de solo lectura (`perm_read=1`, `perm_write=0`, `perm_create=0`, `perm_unlink=0`) sobre `auditlog.log`, `auditlog.rule` y `auditlog.log.line`, además de lectura sobre `ir.model.fields`, `ir.model` e `ir.actions.todo`. El permiso es de consulta del informe de auditoría, no de administración de qué se audita.

#### Scenario: Usuario del grupo intenta modificar una regla de auditoría

- **WHEN** un usuario con solo el grupo "Informe de auditoría Seniat" intenta crear, modificar o eliminar un `auditlog.rule`
- **THEN** la operación es denegada por ACL, porque el grupo solo tiene `perm_read` sobre ese modelo
