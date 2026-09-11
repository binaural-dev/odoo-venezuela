## Why

La pantalla "Pago exitoso" (`point_of_sale.ReceiptScreen`), la que aparece al
validar el pago junto con la impresión del voucher, muestra en su recuadro
verde el total de la FACTURA, no lo que el cliente acaba de pagar. El core
pinta `orderAmountPlusTip` (= `order.priceIncl` menos propina) y `l10n_ve_pos`
le añade al lado el mismo total convertido con
`get_foreign_total_with_tax()`. Ninguno de los dos contempla el recargo IGTF,
que no es un impuesto de línea y por tanto nunca entra en `amount_total`.

Repro de Jesús (2026-07-28):

| Concepto            | Bs        | $     |
|---------------------|-----------|-------|
| Factura             | 12.806,40 | 17,37 |
| Pago con IGTF       |  7.372,30 | 10,00 |
| IGTF generado (3%)  |    221,17 |  0,30 |
| Pago en Bs          |  5.655,27 |  7,67 |
| **Total pagado**    | **13.027,57** | **17,67** |

La pantalla confirmaba "12.806,40 Bs.F / $ 17,37" — 221,17 Bs menos de lo
cobrado — mientras el backend ya había dado la orden por pagada contra
13.027,57 (`pos.order::_get_total_with_igtf()`, `amount_total + igtf_amount`).

## What Changes

- Nuevos getters en `PosOrder` (`order_model.js`):
  - `get_total_paid_with_igtf()` = `get_total_without_igtf() + igtf_amount`,
    redondeado con `_igtfRoundLocal`. Espejo exacto del backend
    `_get_total_with_igtf()`.
  - `get_foreign_total_paid_with_igtf()` = `get_foreign_total_with_tax() +
    foreign_igtf_amount`, redondeado con `roundForeignMoney`. Suma los dos
    foráneos YA derivados (una sola conversión cada uno) en vez de convertir
    la suma local: así el total en pantalla es exactamente la suma de las
    partes que ve el cajero, y se conserva el manejo de tasa histórica que
    `get_foreign_total_with_tax()` hace en reembolsos.
- Nuevo `receipt_screen.js` que parchea `ReceiptScreen.prototype`:
  - `orderAmountPlusTip` — copia del getter del core con `+ igtf_amount`
    (el core formatea la cadena y le concatena la propina dentro del propio
    getter, no hay hook componible). Sin IGTF delega en `super()`, así que un
    cambio del core solo puede afectar a la rama con IGTF. REVISAR EN CADA
    UPGRADE.
  - `foreignOrderAmountWithIgtf` — sustituye el total foráneo de
    `l10n_ve_pos`; sin IGTF devuelve exactamente
    `get_foreign_total_with_tax()`, es decir, comportamiento idéntico al
    actual.
  - `igtfAmount` / `igtfAmountLabel` / `foreignIgtfAmountLabel` para el
    desglose.
- Nuevo `receipt_screen.xml` que hereda `point_of_sale.ReceiptScreen`:
  - Reemplaza el `<t t-out="…get_foreign_total_with_tax()"/>` que inserta
    `l10n_ve_pos` por `foreignOrderAmountWithIgtf`. Se localiza por
    `contains(@t-out, 'get_foreign_total_with_tax')` y no por posición
    (`span[2]`), porque ese `<span>` no tiene clase ni id y su índice depende
    del orden de inserción de `l10n_ve_pos`.
  - Añade bajo el total un renglón discreto "IGTF: 221,17 Bs / $ 0,30"
    (`t-if="igtfAmount"`), para que el cajero vea por qué el monto confirmado
    no coincide con el total de la factura.

### El IGTF aquí es el REAL cobrado, no el 3% fijo

`get_total_paid_with_igtf()` NO es `get_total_with_igtf()` (el getter que
alimenta el renglón "TOTAL a Pagar con IGTF" del panel de estado de pago, ver
`l10n-ve-pos-igtf-total-payment-status`). Aquel es un valor de referencia fijo
—3% de la factura completa— porque durante el cobro aún no se sabe cuánto se
pagará con métodos `apply_igtf`. En la pantalla de recibo la orden ya está
validada: el IGTF a mostrar es `igtf_amount`, el que efectivamente se generó
sobre la base cubierta por líneas `apply_igtf`. En el repro son 221,17
(3% de 7.372,30), no 384,19 (3% de 12.806,40).

Ninguno de los dos toca `get_total_with_tax()` /
`get_foreign_total_with_tax()`, que siguen siendo la conversión pura de
factura compartida con `l10n_ve_pos` (subtítulo nativo, recibo, ticket,
resumen de venta, backend `foreign_amount_total`) — ver
`migration-lessons.md`, "Resuelto 2026-07-14".

## Capabilities

### Modified Capabilities
- `frontend-display`: el recuadro "Pago exitoso" muestra el total realmente
  cobrado (factura + IGTF generado) en ambas monedas, más el desglose del
  recargo.

## Impact

- Módulo: `l10n_ve_pos_igtf` (frontend POS), rama
  `19.0_mig-ta_76667_full_refund_v17_to_v19`.
- Archivos: `static/src/app/overrides/models/order_model.js` (dos getters
  nuevos), `static/src/app/overrides/screens/receipt_screen.js` (nuevo),
  `static/src/app/overrides/screens/receipt_screen.xml` (nuevo).
- Sin cambios de backend ni de contabilidad; solo display.
- Fuera de alcance: el voucher impreso (`OrderReceipt`) sigue sin línea de
  IGTF; y la reimpresión desde la lista de órdenes de una sesión ya cerrada
  cae al comportamiento nativo, porque `igtf_amount` es una prop JS plana y
  no se recarga del backend (no puede declararse en `_load_pos_data_fields`
  sin colgar el POS — ver comentario en `models/pos_order.py`).
