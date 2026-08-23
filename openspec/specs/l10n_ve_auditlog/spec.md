# l10n_ve_auditlog

## Purpose

Consola de auditoría funcional sobre el tracking nativo del chatter: enriquece `mail.tracking.value` con el modelo y el autor del cambio, y expone menús de "Audit logs" filtrados a los documentos contables de la localización (`account.move`, `account.payment` y `account.retention`). Depende de `l10n_ve_accountant` y `l10n_ve_payment_extension` (que aporta el modelo `account.retention`). Es independiente de `l10n_ve_auditlog_base`, que audita a nivel técnico con el módulo OCA `auditlog`.

## Requirements

### Requirement: Modelo y autor en los valores de tracking

El modelo `mail.tracking.value` DEBE (MUST) contar con los campos almacenados `model` (computado desde `mail_message_id.model`) y `author_id` (Many2one a `res.partner`, computado desde `mail_message_id.author_id`), que permiten listar y agrupar las líneas de auditoría por documento y por autor.

#### Scenario: Cambio rastreado en una factura

- **WHEN** un usuario modifica un campo con tracking de un documento y se genera el valor de seguimiento
- **THEN** la línea de tracking registra el modelo del documento y el autor del mensaje asociado

### Requirement: Vista de logs de auditoría sobre documentos contables

La acción "Audit logs" DEBE (MUST) listar los mensajes (`mail.message`) cuyo `model` esté en `account.move`, `account.payment` o `account.retention`, mostrando autor, modelo, asunto, `res_id` y fecha, con filtros de agrupación por modelo, día y autor.

#### Scenario: Consulta de auditoría

- **WHEN** un usuario abre el menú "Audit logs"
- **THEN** solo aparecen mensajes de facturas, pagos y retenciones

### Requirement: Vista de líneas de auditoría con valores anterior y nuevo

La acción "Audit logs lines" DEBE (MUST) listar los registros de `mail.tracking.value` cuyo `model` esté en `account.move`, `account.payment` o `account.retention`, mostrando por línea el campo modificado, el autor y los pares de valores anterior/nuevo de cada tipo (char, datetime, float, integer, text, monetary).

#### Scenario: Revisión de un cambio de monto

- **WHEN** un auditor abre "Audit logs lines" tras un cambio en un campo monetario de un pago
- **THEN** la línea muestra el campo, el autor y el valor monetario anterior y el nuevo
