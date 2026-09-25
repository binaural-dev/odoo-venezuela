# Fix: retención de IVA/ISLR permitía comprobante duplicado

## Why

Ticket de helpdesk #15337: **"Retención de IVA/ISLR permite comprobante
duplicado para el mismo cliente/proveedor"**.

`account.retention` no tenía `copy=False` en `number`, `state`,
`correlative`, `retention_line_ids` ni `payment_ids`. Por el
comportamiento por defecto del ORM (`copy_data()` copia todo campo sin
`copy=False`, incluyendo one2many de forma recursiva), duplicar una
retención desde la vista de lista producía:

- Un duplicado con el **mismo `number`** que el original (el número de
  comprobante fiscal, que debería ser único).
- Un duplicado con el **mismo `state`** (si el original estaba
  "Emitida", el duplicado también nacía "Emitida", con el mismo número).
- `retention_line_ids` duplicadas, apuntando a las mismas facturas ya
  retenidas por el original.
- `payment_ids` duplicados, intentando clonar los pagos reales
  (`account.payment`) asociados.

Tampoco existía ninguna validación bloqueando que un usuario escribiera
manualmente el mismo `number` en dos retenciones (el campo es editable, y
requerido cuando `type == 'out_invoice'`).

## What Changes

- `l10n_ve_payment_extension/models/account_retention.py`
  - `copy=False` en `number`, `state`, `correlative`,
    `retention_line_ids`, `payment_ids`. Duplicar una retención ahora la
    deja en borrador, sin número, sin líneas ni pagos - `create()` ya
    llama a `_set_sequence()`, que asigna un número nuevo y único
    automáticamente en cuanto detecta que `number` está vacío (sin
    necesidad de lógica adicional).
  - Nueva `@api.constrains("number", "company_id", "type_retention")
    _check_number_unique()`: bloquea guardar si ya existe otra retención
    con el mismo `number` en la misma compañía y el mismo
    `type_retention`. Se escogió ese alcance (no global) porque IVA,
    ISLR y municipal usan secuencias de control independientes
    (`retention.<type>.control.number`).
- `l10n_ve_payment_extension/tests/test_retention_duplicate_and_number_unique.py`
  (nuevo)
  - Duplicar una retención emitida resetea `number`/`state`/líneas/pagos.
  - Crear dos retenciones con el mismo `number` para el mismo
    `type_retention` lanza `ValidationError`.
  - El mismo `number` en `type_retention` distintos SÍ está permitido
    (secuencias independientes).
- `l10n_ve_payment_extension/tests/test_retention_ti14548_rules.py`
  - Se corrige un descuido preexistente: el helper
    `_make_islr_customer_retention` hardcodeaba el mismo `number` en
    todos sus llamados; un test creaba dos retenciones ISLR con ese mismo
    número dentro de la misma transacción para probar una regla distinta
    (base de concepto excedida entre retenciones). La nueva constraint de
    unicidad lo detectó correctamente. Se agrega el mismo parámetro
    `number=` que ya tenía su helper gemelo de IVA, y se usan números
    distintos en ese test.

## Post-review fix (code review PR #1368)

Code review de `pastor-binaural` (2026-09-25): `CHANGES_REQUESTED`,
bloqueante sobre esta capability.

El alcance original de `_check_number_unique()` (`company_id` +
`type_retention`) era más amplio de lo que pedía el ticket - que pide
bloquear el mismo número **para el mismo cliente o el mismo
proveedor**, no para cualquier retención del mismo tipo en la compañía.
Sin `partner_id` en el dominio, la constraint bloqueaba casos legítimos:

- Dos **clientes distintos** (`out_*`) entregando el mismo número de
  comprobante (ellos son quienes lo emiten, con su propio correlativo -
  dos clientes pueden coincidir en número sin que sea un duplicado real).
- Una retención de **cliente contra una de proveedor**: la de proveedor
  recibe su número de nuestra secuencia interna `no_gap` en `create()`;
  si un cliente ya había entregado un comprobante con ese mismo valor,
  la creación de la retención de proveedor fallaba - y como el rollback
  no consume el `no_gap`, el mismo número se repetía en cada reintento,
  bloqueando la emisión de cualquier retención de proveedor de ese tipo.
- **Municipal por sucursal** (`binaural_subsidiary_payment_extension`):
  dos sucursales generan correlativos iguales dentro de la misma
  compañía, así que la segunda quedaba bloqueada.
- Retenciones **anuladas** (`state = 'cancel'`) también contaban como
  duplicado, impidiendo re-registrar el comprobante correcto tras
  anular una carga errónea.

### Fix aplicado

- `_check_number_unique()`: el dominio de búsqueda de duplicados ahora
  agrega `partner_id` y agrupa por dirección del comprobante (`in_*`
  vs. `out_*`, ya que cliente y proveedor usan series independientes -
  la del cliente sobre su propio correlativo, la nuestra sobre el
  `no_gap`), y excluye `state = 'cancel'`.
- Tests nuevos: mismo número con partners distintos (permitido), y
  mismo número entre una retención de proveedor y una de cliente del
  mismo partner (permitido, series independientes).

### Sugerencia de follow-up evaluada y descartada

El review también sugería, como no bloqueante, que `create()` dejara de
llamar `_set_sequence()` para retenciones de cliente (`out_*`), asumiendo
que ese número siempre lo entrega el cliente. Se probó ese cambio y la
suite completa del módulo lo contradice: `test_withholdings_islr.py` y
`test_withholdings_iva_partner.py` verifican explícitamente que una
retención de cliente (IVA u ISLR) creada en borrador desde
`invoice.generate_islr_retention` / `generate_iva_retention` **debe**
recibir un auto-número de nuestra secuencia al crearse (comentarios en
el propio test: "Customer retention gets auto-number in draft"). Ese
número es un placeholder de borrador que luego se sobreescribe con el
número real del cliente antes de emitir (ver
`test_iva_customer_post_and_cancel_all_fields`, que hace
`ret.number = "12345678901234"` antes de `action_post()`). No se aplicó
ese follow-up: el comportamiento actual de `_set_sequence()` en
`create()` queda sin cambios.

## Impact

- **Capability**: `retention-voucher-number-uniqueness` (nueva).
- **Módulo**: `l10n_ve_payment_extension`.
- **Riesgo**: bajo. `copy=False` es aditivo (nunca destruye datos
  existentes, solo cambia qué se copia al duplicar) y la constraint solo
  bloquea un estado que ya era inválido en la práctica (el mismo partner
  entregando/recibiendo dos veces el mismo comprobante). Verificado que
  no rompe ningún flujo de creación existente corriendo la suite
  completa del módulo.
- **Verificado**: tests dirigidos y suite completa del módulo (432 tests)
  corridos en contenedor Docker sobre bases de datos limpias; sin fallos
  tras el ajuste de `test_retention_ti14548_rules.py`. Tras el fix
  post-review, se corrió de nuevo la suite dirigida
  (`retention_duplicate_and_number_unique`, 5 tests, incluye los 2 tests
  nuevos) y la suite completa del módulo (434 tests) en contenedor
  Docker sobre bases limpias: sin fallos. El intento inicial de aplicar
  también el follow-up del `_set_sequence()` sí rompió 5 tests
  existentes - se detectó con esta misma suite completa y se revirtió
  antes de cerrar el fix.
