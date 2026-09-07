# Proposal: Mostrar el descuento del PoS sobre la base imponible (sin IVA)

## Intent

En cajas configuradas con **impuestos incluidos** (`pos.config.iface_tax_included == "total"`)
el core de Odoo 19 pinta cada línea de la orden con IVA, incluida la línea de
descuento generada por `pos_discount`. Como esa línea se crea sobre la **base
imponible** con su impuesto asociado (el motor de impuestos reduce base e IVA
por separado), el cajero ve el descuento **más su IVA** (p. ej. `1,08` en lugar
de `1,00` con IVA al 8%), que no coincide con el monto que imprime la máquina
fiscal (que muestra la reducción de base).

Este cambio hace que **solo la línea de descuento** se muestre por su monto
sobre la base imponible (sin IVA), tanto en moneda local como en divisa, en
carrito y recibo, sin alterar el dato subyacente ni el resto del carrito.

## Scope

### In Scope
- `static/src/overrides/models/pos_order_line.js`: getters `displayPrice` y
  `displayPriceUnit` para la línea de descuento devuelven el neto sin IVA;
  nuevo `get_foreign_display_price()` (sin IVA para la línea de descuento).
- `static/src/overrides/components/orderline/orderline.xml`: el monto en divisa
  por línea usa `get_foreign_display_price()` en vez de
  `get_foreign_price_with_tax()`.
- Detección de la línea de descuento vía `pos.config.discount_product_id`.

### Out of Scope
- El **cálculo** del descuento (ya es sobre la base imponible, sin cambios).
- El dato de la línea de descuento: conserva `price_unit` e impuesto para que
  base y total se computen correctamente.
- El ticket de la máquina fiscal (`l10n_ve_pos_mf`) y su driver.
- Cambiar `iface_tax_included` a nivel de configuración.

## Approach

El precio mostrado de cada línea sale de un único getter del core
(`PosOrderAccounting.displayPrice`), que devuelve `priceIncl` cuando la caja está
en `"total"`. Se intercepta ese getter **solo para la línea de descuento** para
devolver `priceExcl` (base). El carrito y el recibo comparten el componente
`Orderline`, así que el override cubre ambas superficies. El monto en divisa por
línea (plantilla `orderline.xml`) se alinea con un método de modelo dedicado.

## Affected Areas

| Área | Impacto |
|------|---------|
| `l10n_ve_pos` modelo `pos.order.line` (JS) | `displayPrice`/`displayPriceUnit` de la línea de descuento devuelven el neto; `get_foreign_display_price` nuevo |
| `l10n_ve_pos` plantilla `Orderline` (XML) | el monto en divisa por línea usa `get_foreign_display_price` |

## Trade-off conocido

Con productos mostrados con IVA y el descuento mostrado sin IVA, las líneas del
recibo del PoS no suman a simple vista por el IVA del descuento (p. ej.
`10,80 − 1,00 ≠ 9,72`; faltan `0,08`). El total es correcto y el ticket fiscal de
la máquina cuadra en su formato base+IVA. Decisión aceptada por el negocio:
mostrar el descuento "real" sobre base imponible.
