## Why

`pos.payment._load_pos_data_fields` (core Odoo 19) returns `[]`, y el mixin
`pos.load.mixin` trata una lista vacía como "cargar todos los campos"
(`_load_pos_data_read` hace `records.read(fields, load=False)`, y el ORM
interpreta `fields=[]` como "todos"). `l10n_ve_pos/models/pos_payment.py`
rompía ese contrato: hacía `res = super()._load_pos_data_fields(config) or
[]` y luego construía una lista explícita (`_POS_PAYMENT_CORE_FIELDS` +
campos foráneos), convirtiendo el "todos los campos" del core en un
whitelist fijo.

Efecto real (db `2doce`, 2026-07-30): al instalar `binaural_subsidiary_pos`
(que depende de `sh_pos_analytic_tags`, un módulo que añade
`sh_analytic_account` a `pos.payment`), el PdV rompía al pulsar un método de
pago: *"The field 'sh_analytic_account' does not exist in model
'pos.payment'"*. El campo existe y se lee bien desde el backend — el
problema es que el whitelist de `l10n_ve_pos` no lo incluye, así que el
motor `related_models` del cliente lo rechaza al hacer `.update()`.

Ya hubo un incidente hermano con el mismo síntoma raíz: el whitelist se creó
originalmente sin `write_date`, lo que colgaba el PdV al abrir
(`constructOrdersDomain` → `record.write_date.plus(...)`) — corregido en
`2b6c958aa` añadiendo `write_date` al whitelist, pero sin cuestionar si
narrowear la lista era necesario en primer lugar. Este change corrige la
causa raíz en vez de seguir parchando síntomas campo por campo.

## What Changes

- `models/pos_payment.py::_load_pos_data_fields`: si `super()` ya devuelve
  una lista vacía (contrato "todos los campos"), se respeta tal cual — no se
  construye un whitelist. Solo se añade `_POS_PAYMENT_CORE_FIELDS` +
  `foreign_rate`/`foreign_amount`/`foreign_currency_id` cuando algún
  ancestro en la cadena YA haya devuelto una lista no vacía.
- Test `test_pos_payment_load_pos_data_fields_includes_foreign_amount_and_rate`
  actualizado al mismo idiom que `test_dynamic_models_expose_write_date`
  (`not fields or "campo" in fields`), en vez de `assertIn` estricto —
  el assertIn estricto es justo lo que hacía pasar el bug desapercibido.

## Capabilities

### New Capabilities

- `pos-payment-fields-contract`: `pos.payment._load_pos_data_fields` respeta
  el contrato "lista vacía = todos los campos" del core en vez de
  reemplazarlo por un whitelist propio (nota: existe un capability
  relacionado `pos-odoo19-data-loading` dentro de
  `openspec/changes/l10n-ve-pos-migration-plan/specs/`, pero ese change aún
  no está archivado/mergeado a `openspec/specs/`, así que no hay un spec
  canónico del que partir un delta MODIFIED todavía).

## Impact

- `src/odoo-venezuela/l10n_ve_pos/models/pos_payment.py`
- `src/odoo-venezuela/l10n_ve_pos/tests/test_pos_serialization.py`
- Desbloquea `binaural_subsidiary_pos` (y cualquier módulo futuro que añada
  un campo a `pos.payment`) sin tener que tocar `l10n_ve_pos` de nuevo cada
  vez.
