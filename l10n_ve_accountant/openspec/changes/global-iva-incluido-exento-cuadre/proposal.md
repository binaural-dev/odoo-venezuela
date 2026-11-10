# Fix: con Global el centavo cae en su grupo de impuesto y el asiento, el widget y el alterno cuadran

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

- Con **Global**, la diferencia de redondeo de la base cae en el **grupo de impuesto al que pertenece** (IVA, Exento…), en su línea de mayor base, y no en la línea de mayor base de toda la factura. Así el Exento no se infla con el centavo del IVA, también en bolívares (el Exento quedaba inflado en un centavo de USD por la tasa: Bs. 8,79 a 879,1225).

- Los montos para el cálculo de impuestos salen de la **moneda de la compañía (VEF)**; el documento y
  el alterno se derivan de ahí y todos cuadran (Debe = Haber en VEF y en alterno).
- Con Global y al menos una línea con IVA incluido, cada línea base vale su importe individual
  (`precio × cantidad × (1 − descuento)`, con el IVA incluido dividido entre `1 + tasa`), tanto en la
  moneda del documento como en la alterna. El total con IVA incluido es lo que digitó el usuario.
- El IVA incluido se calcula **línea por línea sobre la base en bolívares**, también cuando el widget lo calcula para un registro virtual (onchange): con Global el servidor ya no manda al guardar el IVA del núcleo (que reparte el centavo), porque `_inverse_tax_totals` lo escribiría como edición manual y el IVA en Bs saldría de `IVA en la moneda del documento × tasa` (factura de compra de 2 × $ 12,95 a 803,34: Bs. 2.867,92 en vez de Bs. 2.869,86 y total de $ 25,89 en vez de $ 25,90).
- El widget (`tax_totals`) refleja los apuntes reales: bases, IVA y total en documento, VEF y alterno, con Global y con Por línea.

## What Changes

- `account.tax` (`models/account_tax.py`):
  - `_prepare_tax_lines` + `_apply_price_included_per_line`: fijan la base de cada línea y el IVA
    incluido por línea (solo `round_globally` y facturas con al menos una línea con IVA incluido).
  - `_fix_base_amount_from_real_lines`: bases del widget (documento y VEF) desde las líneas reales
    (Global y Por línea, con impuestos incluidos); cada subtotal parte del total del anterior.
  - `_fix_foreign_summary_from_lines`: alterno del widget desde `foreign_debit`/`foreign_credit`.
  - `_round_tax_details_base_lines` + `_get_base_line_rounding_key`: con Global reparte la diferencia
    de redondeo de la base dentro de cada grupo de impuesto (antes, entre todas las líneas).
  - `_fix_price_included_summary_from_base_lines`: en un registro virtual (o sin líneas de impuesto),
    el IVA incluido del resumen se calcula línea por línea, igual que `_sync_tax_lines`.
  - `_get_tax_group_product_lines`: líneas de un grupo de impuesto (antes duplicado en línea).
- Bump `19.0.1.0.42` -> `19.0.1.0.43`.
- `tests/test_global_price_included_exempt.py`: 12 pruebas (USD, VEF, EUR, factura de compra con IVA incluido a distintas tasas, mezcla con IVA excluido,
  control sin exento, exento incluido en el precio, base VEF del IVA, subtotales encadenados, el centavo
  en su grupo en USD/EUR/VEF, grupo exento con dos líneas y widget con Por línea).

## Impacto a revisar

- **El total del documento con Global sigue el redondeo por grupo**, no el del documento entero. Con IVA
  excluido y precios de 4 decimales, ambas definiciones difieren en un centavo en 12 de 36 facturas de
  prueba; frente a la versión anterior de este cambio, el total del asiento varió ±0,01 en 21 de 216 facturas
  (todas con Global; con Por línea ninguna).
- **POS:** el POS calcula en el frontend (`account_tax.js`) con el redondeo del documento entero. No se
  probó si una venta de POS con precios de más de 2 decimales queda con 0,01 de diferencia entre el total
  del POS y el de su factura; replicar el criterio en el POS queda fuera de este módulo.

- Los apuntes y los totales con **Por línea** o con IVA solo excluido no cambian.
- El alterno del widget ahora sale de los apuntes también en Por línea (cambia en facturas en una
  tercera moneda, p. ej. EUR, donde el widget y el apunte diferían hasta 0,02).
- No se modifican facturas ya publicadas; un borrador recalculado puede cambiar un centavo.
- No cubierto: notas de crédito/débito, POS, órdenes de venta/compra, impuestos con varias tasas por línea.
