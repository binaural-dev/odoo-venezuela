# Fix: la retención ISLR de cliente no calculaba con una sucursal como empresa activa

## Why

Ticket de helpdesk #16438 (Daiko Premium): con una sucursal como empresa
activa, la línea de la retención ISLR de cliente se creaba con total de
factura, % base imponible, % tarifa y monto retenido en 0, sin ningún
error. Con la casa matriz activa la misma factura calculaba bien.

`account.retention.line._get_islr_type_person_id()` toma, para ISLR de
cliente, `company_id.partner_id.type_person_id` (la empresa activa).
`_compute_related_fields()` solo asigna los campos si alguna línea del
concepto coincide con ese tipo de persona. El contacto de la sucursal
nacía con `type_person_id`, `withholding_type_id` y `taxpayer_type`
vacíos o por defecto, ninguna línea coincidía y el cálculo terminaba sin
asignar nada ni avisar.

Las sucursales comparten la identidad fiscal de la casa matriz, así que
esos datos no deben configurarse por separado en cada sucursal.

## What Changes

- `l10n_ve_payment_extension/models/res_partner.py`
  - `_l10n_ve_branch_synced_fields()`: lista de campos fiscales que las
    sucursales heredan (`type_person_id`, `withholding_type_id`,
    `taxpayer_type`).
  - `_l10n_ve_propagate_fiscal_fields_to_branches()`: copia esos campos del
    contacto de una compañía raíz a los contactos de todas sus sucursales
    (`child_of`, incluidas las archivadas). Acepta `fnames` opcional (por
    defecto todos) que usa la migración para copiar solo los campos con
    valor en la raíz.
  - `_fields_sync()`: al escribir alguno de esos campos en el contacto de
    la compañía raíz, llama a la propagación (único gancho del core que
    recibe solo los campos cambiados; el sync comercial del core va por el
    `parent_id` del contacto y los contactos de las sucursales no cuelgan
    del de la matriz).
  - `@api.constrains` `_l10n_ve_check_branch_fiscal_fields()`: bloquea que
    el contacto de una sucursal tenga un valor distinto al de su raíz.
- `l10n_ve_payment_extension/models/res_company.py`
  - `create()` (multi): al crear una sucursal, aplica a su contacto los
    valores de la raíz (el core solo copia campos de `res.company`).
- `l10n_ve_payment_extension/migrations/19.0.2.2.9/`: iguala los contactos
  de las sucursales existentes a los de su raíz, sobrescribiendo lo que
  tuvieran, pero solo los campos que tienen valor en la raíz: un campo
  vacío en la raíz no se toca en las sucursales. Se deja un `warning` por
  cada valor de sucursal que se sobrescribe y por cada valor que se
  conserva por tener la raíz el campo vacío.
- `l10n_ve_payment_extension/tests/test_branch_fiscal_propagation.py`
  (nuevo): propagación (incluye sucursal de sucursal), bloqueo, sucursal
  nueva, migración (sobrescritura y warning) y tipo de persona de la
  retención ISLR de cliente con la sucursal activa.

## Non-goals

- No se toca `_get_islr_type_person_id()`: con los datos propagados el
  cálculo ya encuentra el tipo de persona.
- No se distingue una sucursal de otro RIF: la propagación aplica a todas
  las sucursales de la raíz.
- No se usa `store=True` ni la lista de campos delegados del core
  (`_get_company_root_delegated_field_names`), que solo aplica a campos de
  `res.company`.
- No se cubre `condition_withholding_id` en el formulario de la compañía de
  una sucursal (ver Impact).
- No se agrega comodidad de UI (campos en solo lectura): la constraint ya
  garantiza la regla.

## Impact

- Overrides nuevos: `res.partner._fields_sync` y `res.company.create`.
  Ambos justificados arriba (no hay otro punto de enganche en el core).
- Riesgo: `_fields_sync` es un método privado del core; el test
  `test_a_root_edit_propagates_to_descendants` fija el comportamiento ante
  cambios entre versiones.
- La migración sobrescribe los valores de las sucursales con los de su
  raíz solo si la raíz tiene valor; si la raíz tiene el campo vacío, la
  sucursal conserva el suyo (con un `warning`). Esa sucursal queda distinta
  a su raíz hasta que se configure la matriz, y la constraint rechazará
  escrituras de ese campo en la sucursal (su mensaje indica dónde editarlo).
  La migración escribe con el contexto `l10n_ve_skip_branch_fiscal_check`,
  que la constraint respeta, para poder propagar los demás campos.
  Conviene revisar los warnings y configurar la matriz después de migrar.
- Caso abierto: `condition_withholding_id` sigue editable en el formulario
  de compañía de una sucursal; el cambio se rechaza con el mensaje del
  contacto.
