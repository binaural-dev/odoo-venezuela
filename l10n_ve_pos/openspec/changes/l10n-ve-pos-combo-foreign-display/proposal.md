# Fix: el monto en divisa de la línea padre de un combo salía en 0 (l10n_ve_pos)

Ticket 15725 — "Ajustes a los montos alternos de los productos tipo combo".

## Why

En Odoo 19 la línea padre de un combo no tiene precio propio: el core reparte
el precio del combo entre las líneas hijas, y el padre muestra la suma de
ellas (`pos_order_line_accounting.js::displayPrice`, que con
`combo_line_ids` suma `priceIncl`/`priceExcl` de las hijas). Las hijas no
muestran precio (`currencyDisplayPrice` = "" con `combo_parent_id`).

La plantilla `orderline.xml` convertía el monto PROPIO de la línea
(`get_foreign_price_with_tax()` / `_without_tax()` → `priceIncl`/`priceExcl`).
En el padre del combo eso es 0, así que la línea mostraba "Bs 680,00 / $ 0,00".
Además, las hijas mostraban el "/ $ x" suelto, sin el precio local al lado.

## What Changes

- **`pos_order_line.js`**: nuevo `get_foreign_display_price()` = el
  `displayPrice` del core convertido UNA sola vez (`_conv`):
  - `displayPrice` ya usa el monto con impuestos si
    `iface_tax_included === 'total'` y sin impuestos si no, y en el padre de un
    combo es la suma de sus `combo_line_ids` (con su precio, descuento y lista
    de precios vigentes);
  - convertir el total una vez (y no sumar las hijas ya convertidas) evita
    acumular el redondeo de cada hija: en una venta el padre cuadra con el
    total foráneo de la orden (`localToForeign(totalDue)`), como pide la regla
    de conversión del fichero.
  `_conv` elige la tasa: en vivo, congelada de la orden sincronizada o, en un
  reembolso, la de la venta original (`_refundOriginalRate`; el padre del
  reembolso también apunta a la línea original). Siempre multiplica.
- **`orderline.xml`**: el monto en divisa usa `get_foreign_display_price()` y
  solo se pinta donde el core pinta el precio (`vals.price`). Las hijas del
  combo y el recibo básico ya no muestran el divisa suelto.
- `get_foreign_price_*` NO cambia: los totales de la orden
  (`_sumForeignLines`) suman esos getters de todas las líneas, y si el padre
  devolviera la suma de sus hijas el combo contaría dos veces.

## Impact

- **Módulo**: `l10n_ve_pos`, solo frontend. Fix visual; no toca totales,
  pagos ni contabilidad.
- **Pantallas**: todas las que usan `point_of_sale.Orderline` (pedido, ticket
  screen, reembolso, recibo, pantalla del cliente).
- `binaural_pos_multicurrency` (integra-addons) hereda esta plantilla para las
  cajas en otra moneda y aplica el mismo criterio con su monto en moneda de la
  compañía.
