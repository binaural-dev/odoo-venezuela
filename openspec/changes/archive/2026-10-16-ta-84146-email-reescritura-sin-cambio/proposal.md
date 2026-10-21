## Why

Backport del fix upstream 4d9361e4 de 19.0 (tarea 84357) a maintenance-19.0, acotado al bug TA 84146. Un usuario portal guarda su dirección desde `/my/address` sin problemas la primera vez, pero al volver a editarla (por ejemplo cambiar la ciudad) el POST a `/my/address/submit` devuelve 422 HTML y el frontend falla al hacer `JSON.parse`. Causa raíz: `write()` de `l10n_ve_contact/models/res_partner.py` re-validaba `check_duplicate_email` en cada escritura que llevara `email`, incluso sin cambio; al reenviar el mismo email choca con la dirección hija creada en el primer guardado, que lo comparte.

## What Changes

- `l10n_ve_contact/models/res_partner.py` `write()`: se calcula `email_changed = self.filtered(...)` antes del `super().write()` y solo se valida `check_duplicate_email` en los registros cuyo email cambió realmente; un `write` que reenvía el email que el contacto ya tiene no se valida. La lógica es idéntica al upstream 19.0.
- Tests: se mantiene la batería de escritura y se agregan (a) `test_write_multi_record_only_changed_fails` (escritura multi-record donde solo un registro cambia el email: falla por el que cambió, no por el que reescribe el mismo), (b) `test_write_unchanged_email_with_child_of_any_type` (reescritura del mismo email con hijos tipo `delivery`/`invoice`/`other` no lanza), (c) `test_write_new_duplicated_email` (cambio de email a uno ajeno sí lanza `ValidationError`); más el escenario TA 84146 `test_portal_address_reedit_unchanged_email` y `test_write_changed_email_on_delivery_address_skips_check`.
- Bump `l10n_ve_contact` 1.8 → 1.9 (versión corta de maintenance, no el formato 19.0.x del upstream).
- Spec `openspec/specs/l10n_ve_contact/spec.md`: requirement "Duplicidad de email en contactos" actualizado — `write` solo valida cuando el email realmente cambia; escenarios "Reescribir el mismo email" y "Dirección de entrega" conservados; se documenta el límite conocido de `write` (cambio de `type` a `contact` con email ajeno no se valida, idéntico al upstream).

## Out of Scope

- Re-validación de duplicidad de email **dentro del mismo lote de `create`** (importaciones en bloque donde dos contactos del lote comparten un email que no existía antes): comportamiento del upstream 4d9361e4 diferido a la tarea 84357. `create()` queda como en `maintenance-19.0` actual.
- Modificar la lógica de `write` respecto del upstream (por ejemplo, validar también cambios de `type`): se documenta como límite conocido, no se cambia.

## Known Limit

`write()` solo observa `email` para decidir qué registros validar. Un `write` que cambia `type` a `contact` (o no lo trae) dejando un email igual al de otro partner **no** dispara `check_duplicate_email`, porque `email_changed` queda vacío. Comportamiento idéntico al upstream 19.0 (4d9361e4); se deja constancia documental, sin cambio de lógica.

## Impact

- Specs: `l10n_ve_contact`.
- Tests: `l10n_ve_contact/tests/test_l1on_ve_contact.py` (13 tests, 2 skipped preexistentes por falta de `sale.order`/`purchase.order`).
- Regresión: 5 módulos website (`binaural_website`, `binaural_website_sale`, `binaural_website_sale_comparison`, `binaural_website_sale_transit`, `binaural_website_sale_delivery`).
- Fix puramente relajante: no bloquea flujos nuevos; solo deja de rechazar reescrituras sin cambio de email.

## Traceability (requirement → task → test)

| Requirement | Task | Test |
|---|---|---|
| Duplicidad de email en contactos — `write` solo valida cambios (event-driven) | tasks 2–5 | `test_write_same_email_on_already_duplicated_partners`, `test_portal_address_reedit_unchanged_email`, `test_write_multi_record_only_changed_fails`, `test_write_unchanged_email_with_child_of_any_type` |
| Duplicidad de email en contactos — cambio a email ajeno lanza (unwanted) | tasks 2, 5 | `test_write_new_duplicated_email`, `test_portal_address_reedit_unchanged_email` |
| Duplicidad de email en contactos — `type != contact` no se valida en `write` | tasks 3, 5 | `test_write_changed_email_on_delivery_address_skips_check` |
| Duplicidad de email en contactos — `create` sin cambio (out of scope 84357) | — | — (sin test en este cambio) |

## Referencias

- Ticket: https://binaural.odoo.com/odoo/action-341/84146
- Upstream: 4d9361e4 (19.0, tarea 84357)
