# Fix: una subsección hace imposible facturar el documento

## Why

Reportado en CDD Las Mercedes (tarea 82254) sobre la cotización **S11508**:
la factura no se podía crear, y una vez sorteado eso, tampoco validar.

`line_subsection` es un `display_type` que **Odoo 19 agregó a la familia de
líneas de maquetado** (`line_section`, `line_note`). Todos los guards de este
módulo tenían las dos tuplas viejas hardcodeadas, así que una subsección
—que por definición tiene `price_unit = 0` y no puede llevar impuesto— era
leída como **línea de producto**:

1. `_check_price_in_zero` la veía como producto a precio cero y lanzaba
   `ValidationError: "An invoice cannot have a line with a price of zero"` al
   **crear** la factura.
2. `action_post` le exigía impuesto y lanzaba `"Add a tax to each product
   line..."` al **validar**. Es decir: arreglar solo el punto 1 no destraba
   nada, mueve el bloqueo de crear a postear.
3. `_check_refund_against_origin` la trataba como producto a acreditar,
   exigiéndole `product_id` en una nota de crédito.

El síntoma es duro y sin salida: cualquier documento que use una subsección
—una función nativa de Odoo 19, disponible en la UI— es infacturable. No hay
workaround más que borrar la subsección.

## What Changes

Se agrega `"line_subsection"` a las tres tuplas de `display_type` del módulo,
para que las tres queden alineadas con la familia completa de líneas de
maquetado:

- `_check_price_in_zero`: la tupla de tipos que se saltea la validación de
  precio cero.
- `_check_refund_against_origin`: `product_line_types`, los tipos que no son
  producto acreditable.
- `action_post`: la tupla que hace `continue` antes de exigir impuesto.

Las tres tuplas quedan explícitamente marcadas en el código como "mantener
en sincronía": son el mismo concepto repetido tres veces, y el bug fue
justamente que se actualizó cero de las tres.

El archivo además pasó por `black`, que es de dónde sale el grueso del diff.
El cambio funcional son tres tuplas.

## Capabilities

### New Capabilities
- `invoice-layout-line-exclusions`: los guards de `l10n_ve_invoice` que
  validan líneas de producto (precio distinto de cero, impuesto obligatorio,
  correspondencia con la factura de origen en notas de crédito) deben excluir
  siempre la familia completa de líneas de maquetado
  (`line_section`, `line_subsection`, `line_note`), sin importar cuál de
  ellas se agregue en una versión futura de Odoo.

## Impact

- Archivo: `l10n_ve_invoice/models/account_move.py`
  (`_check_price_in_zero`, `_check_refund_against_origin`, `action_post`).
- Archivo: `l10n_ve_invoice/tests/test_account_move_extended.py` (un test
  extendido y renombrado, uno nuevo).
- Módulos afectados: cualquier cliente con `l10n_ve_invoice` en Odoo 19 que
  use subsecciones en facturas, cotizaciones facturadas o notas de crédito.
- **Bloquea a otros repos.** El fix de secciones con combos en
  `cdd-las-mercedes` (`cdd_account`, `cdd_sections`) no se puede verificar en
  ambiente sin esto: la factura de S11508 no llega a crearse. Este cambio
  tiene que mergearse primero.
- Ver también el cambio hermano en `l10n_ve_accountant`
  (`l10n-ve-subsection-foreign-value-zero`), que corrige la misma omisión en
  el cálculo del importe en moneda alterna.
- Sin migración de datos: los guards impedían persistir cualquier cosa. Los
  documentos afectados quedaban trabados en borrador o sin poder crearse,
  nunca llegaron a la base con datos inválidos.
- Bump de manifest `19.0.1.0.12` → `19.0.1.0.13`.
