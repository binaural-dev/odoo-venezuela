# l10n_ve_auditlog

## Purpose

Consola de auditoría funcional sobre el tracking nativo del chatter: enriquece `mail.tracking.value` con el modelo y el autor del cambio, y expone menús de "Audit logs" filtrados a los documentos contables de la localización (`account.move`, `account.payment` y `account.retention`). Depende de `l10n_ve_accountant` y `l10n_ve_payment_extension` (que aporta el modelo `account.retention`). Es independiente de `l10n_ve_auditlog_base`, que audita a nivel técnico con el módulo OCA `auditlog`. El módulo no declara ACL ni grupos propios: la visibilidad depende de los permisos nativos sobre `mail.message` y `mail.tracking.value`, y el menú raíz "Audit logs" no lleva atributo `groups`.

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

La acción "Audit logs lines" (`l10n_ve_mail_tracking_value_audits_action`) DEBE (MUST) abrir `mail.tracking.value` en modo `list,form` con el dominio `[('model', 'in', ('account.move','account.payment','account.retention'))]`, mostrando por línea `model`, `field`, `author_id`, `field_type` y los pares anterior/nuevo de cada tipo (`*_value_char`, `*_value_datetime`, `*_value_float`, `*_value_integer`, `*_value_text`, `*_value_monetary`). La vista de búsqueda que acompaña al archivo (`l10n_ve_auditlog_lines_search`) está declarada sobre el modelo `mail.message`, no sobre `mail.tracking.value`, por lo que la lista de líneas no recibe esos filtros de agrupación.

#### Scenario: Revisión de un cambio de monto

- **WHEN** un auditor abre "Audit logs lines" tras un cambio en un campo monetario de un pago
- **THEN** la línea muestra el modelo, el campo, el autor y el valor monetario anterior y el nuevo

#### Scenario: Agrupar las líneas por autor

- **WHEN** el auditor busca en "Audit logs lines" los agrupamientos por modelo, día o autor
- **THEN** no están disponibles, porque la vista de búsqueda del módulo apunta a `mail.message`
