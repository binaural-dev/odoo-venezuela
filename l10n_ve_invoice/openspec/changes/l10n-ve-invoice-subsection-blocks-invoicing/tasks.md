# Tasks

## 1. Diagnóstico

- [x] 1.1 Reproducido sobre la cotización S11508 de CDD Las Mercedes: la
      factura no se puede crear
- [x] 1.2 Identificado `line_subsection` como `display_type` nuevo de Odoo 19
      en la familia de líneas de maquetado, ausente de las tuplas del módulo
- [x] 1.3 Confirmado que `_check_price_in_zero` la lee como producto a
      precio cero (`price_unit = 0` por definición en una subsección)
- [x] 1.4 Confirmado que arreglar solo `_check_price_in_zero` NO destraba el
      flujo: `action_post` exige impuesto y mueve el bloqueo de crear a
      validar
- [x] 1.5 Auditadas todas las tuplas de `display_type` del módulo: aparecen
      tres, las tres incompletas

## 2. Fix

- [x] 2.1 Agregar `"line_subsection"` a la tupla de `_check_price_in_zero`
- [x] 2.2 Agregar `"line_subsection"` a `product_line_types` en
      `_check_refund_against_origin`
- [x] 2.3 Agregar `"line_subsection"` a la tupla de `action_post`
- [x] 2.4 Comentario en el código marcando las tres como "mantener en
      sincronía" -- el bug fue que se actualizó cero de las tres
- [x] 2.5 Bump de manifest `19.0.1.0.12` → `19.0.1.0.13`

## 3. Tests de regresión

- [x] 3.1 `test_price_in_zero_ignores_section_and_note` extendido con una
      línea `line_subsection` y renombrado a
      `test_price_in_zero_ignores_layout_lines`
- [x] 3.2 Nuevo `test_action_post_does_not_demand_a_tax_on_layout_lines`:
      cubre el segundo bloqueo, que el primer test no toca. Sin este, un fix
      parcial pasaría los tests y seguiría sin poder facturarse
- [x] 3.3 El test de posteo usa el contexto `move_action_post_alert=True`:
      `l10n_ve_accountant.action_post()` devuelve el wizard de alerta para
      `out_invoice`/`out_refund` salvo que esté esa clave, y sin ella la
      factura queda en draft y el test no prueba nada. Es la convención que
      ya usa el suite de `l10n_ve_invoice_digital`

## 4. Verificación

- [x] 4.1 Suite completa de `l10n_ve_invoice` en base fresca
      (`-i l10n_ve_invoice --without-demo=all`): 146/146
- [x] 4.2 Confirmado que la suite NO corre contra base clonada: su `setUp`
      pisa `company.foreign_currency_id` y `l10n_ve_rate` lo rechaza ("La
      moneda alterna actual ya tiene movimientos contables"). Los ~30 tests
      de la clase fallan por esa causa, no por el fix
- [x] 4.3 Verificado en el ambiente de CDD que la factura de S11508 se crea
      y se valida con este fix más el de `l10n_ve_accountant`
- [x] 4.4 `TestRealPortion.test_34_line_section_never_receives_real_portion_residual`
      (l10n_ve_accountant) falla con `l10n_ve_invoice` instalado: crea líneas
      con `tax_ids: [(5, 0, 0)]` y postea, chocando con la exigencia de
      impuesto de `action_post`. **PREEXISTENTE**, comprobado con
      `git stash` -- incompatibilidad cruzada entre los dos módulos, no
      regresión de este cambio

## 5. OpenSpec

- [x] 5.1 `proposal.md` + spec delta
- [x] 5.2 `openspec validate --changes` -> 2 passed, 0 failed
