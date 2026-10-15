# Fix: el reembolso a tasa exacta no ajustaba a la deuda en el límite de un céntimo (l10n_ve_pos)

## Why

Tarea 83148, hallazgo H20 (06-oct-2026, al pasar el hoot completo). En un
reembolso con la tasa exacta del pago foráneo original
(`l10n-ve-pos-refund-payment-original-rate`, ticket #15114), la línea espeja lo
tecleado (|foráneo| × tasa exacta) y solo se ajusta a la deuda local exacta si
lo tecleado está a un paso foráneo de la deuda. Esa comparación se hacía en Bs
y con flotantes crudos: `|directo − deuda| ≤ tasa × 0,01`. Con tasa 40 y
90,01 $ contra una deuda de 3.600 Bs la diferencia es 0,40000000000009 > 0,40,
así que la línea quedaba en −3.600,40 en vez de −3.600 y sobraban 0,40 Bs. El
propio test del #15114 ("snap solo dentro de un paso foráneo") falla en
origin/19.0 desde el merge del PR #1326 (el hoot no se debió de correr; en
posv19 estuvo bloqueado hasta el 05-oct por módulos ajenos).

## What Changes

- **`static/src/overrides/models/payment_model.js`** (`set_foreign_amount`,
  rama de tasa exacta): la decisión se toma en la moneda tecleada con la
  comparación de la moneda, como en la rama de ventas. La deuda en divisa sale
  multiplicando la deuda local por `1 / tasa exacta`, se redondea a la divisa
  (la deuda que ve el cajero) y hay snap si lo tecleado está a un paso o menos
  (`currency.comp`, que redondea antes de comparar). Sin `comp` (moneda sin
  resolver), la misma regla con `roundPrecision` y medio paso de margen.
- Espejo (sobrepago, parcial) y signo, sin cambios.

## Non-goals

- Cambiar el change del #15114 (ya mergeado): este lo complementa. Al
  archivar, `l10n-ve-pos-refund-payment-original-rate` va antes que este (los
  dos tocan `pos-refund-original-rate`).

## Impact

- Con deudas en céntimos exactos de divisa el resultado es el mismo salvo en el
  límite, que ahora ajusta. Con una deuda que no cae en el céntimo (−3.600,25 Bs
  a 40 = 90,00625 $, mostrada 90,01 $) el paso se cuenta desde la deuda
  mostrada: 90,00 y 90,02 ajustan, 89,99 espeja.
- Tests: `static/tests/unit/payment_model.test.js` (límites por arriba y por
  abajo, deuda fuera del céntimo, tasa no entera, moneda sin resolver).
