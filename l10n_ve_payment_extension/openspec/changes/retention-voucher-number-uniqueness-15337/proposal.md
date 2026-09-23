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

## Impact

- **Capability**: `retention-voucher-number-uniqueness` (nueva).
- **Módulo**: `l10n_ve_payment_extension`.
- **Riesgo**: bajo. `copy=False` es aditivo (nunca destruye datos
  existentes, solo cambia qué se copia al duplicar) y la nueva
  constraint solo bloquea un estado que ya era inválido en la práctica
  (dos comprobantes fiscales con el mismo número). Verificado que no
  rompe ningún flujo de creación existente corriendo la suite completa
  del módulo.
- **Verificado**: tests dirigidos y suite completa del módulo (432 tests)
  corridos en contenedor Docker sobre bases de datos limpias; sin fallos
  tras el ajuste de `test_retention_ti14548_rules.py`.
