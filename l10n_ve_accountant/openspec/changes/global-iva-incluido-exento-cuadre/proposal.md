# Fix: Global + IVA incluido + línea exenta cuadra el asiento, el widget y el alterno

## Why

Con el método de redondeo **Global** (`round_globally`), una factura con impuestos incluidos en el
precio y una línea exenta (o una línea con IVA excluido de mayor base) podía quedar con el **total del
asiento 0,01 distinto de lo digitado**, el widget `tax_totals` distinto del asiento y el alterno del
widget distinto del de los apuntes. Por línea no tenía el defecto.

## Causa

- El motor de impuestos del núcleo (`account.tax._prepare_tax_lines`, `round_globally`) reparte el
  centavo del redondeo global entre las líneas base (cae en la de mayor base, p. ej. la exenta) y lo
  compensa en la línea de IVA. Eso es comportamiento nativo.
- `account.move._sync_tax_lines` reemplaza luego el IVA incluido por la suma línea por línea (regla
  VEF primero: el impuesto se calcula sobre los saldos en la moneda de la compañía), pero la línea
  exenta conserva el centavo del núcleo: la compensación se pierde y el total queda 0,01 distinto.
- `_fix_tax_amount_for_round_per_line` tomaba el IVA de las líneas de impuesto reales pero dejaba la
  base calculada por el núcleo (redondeo global), y el alterno del widget se calculaba aparte.

## Regla

- Los montos para el cálculo de impuestos salen de la **moneda de la compañía (VEF)**; el documento y
  el alterno se derivan de ahí y todos cuadran (Debe = Haber en VEF y en alterno).
- Con Global y al menos una línea con IVA incluido, cada línea base vale su importe individual
  (`precio × cantidad × (1 − descuento)`, con el IVA incluido dividido entre `1 + tasa`), tanto en la
  moneda del documento como en la alterna. El total con IVA incluido es lo que digitó el usuario.
- El widget (`tax_totals`) refleja los apuntes reales: bases, IVA y total en documento, VEF y alterno.

## What Changes

- `account.tax` (`models/account_tax.py`):
  - `_prepare_tax_lines` + `_apply_price_included_per_line`: fijan la base de cada línea y el IVA
    incluido por línea (solo `round_globally` y facturas con al menos una línea con IVA incluido).
  - `_fix_base_amount_from_real_lines`: bases del widget (documento y VEF) desde las líneas reales;
    cada subtotal parte del total del anterior.
  - `_fix_foreign_summary_from_lines`: alterno del widget desde `foreign_debit`/`foreign_credit`.
  - `_get_tax_group_product_lines`: líneas de un grupo de impuesto (antes duplicado en línea).
- Bump `19.0.1.0.42` -> `19.0.1.0.43`.
- `tests/test_global_price_included_exempt.py`: 8 pruebas (USD, VEF, EUR, mezcla con IVA excluido,
  control sin exento, exento incluido en el precio, base VEF del IVA y subtotales encadenados).

## Impacto a revisar

- Los apuntes y los totales con **Por línea** o con IVA solo excluido no cambian.
- El alterno del widget ahora sale de los apuntes también en Por línea (cambia en facturas en una
  tercera moneda, p. ej. EUR, donde el widget y el apunte diferían hasta 0,02).
- No se modifican facturas ya publicadas; un borrador recalculado puede cambiar un centavo.
- No cubierto: notas de crédito/débito, POS, órdenes de venta/compra, impuestos con varias tasas por línea.
