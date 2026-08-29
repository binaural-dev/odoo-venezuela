# Design: redondeo del precio unitario a la moneda principal

## Decisión de fondo: alinear Odoo a la MF, no la MF a Odoo

La MF sólo maneja el precio de ítem con 2 decimales y hace *redondear el
unitario → multiplicar por la cantidad*. Odoo trabaja el unitario con la
precisión del catálogo (DP "Product Price" = 6) y hace *multiplicar →
redondear*. Con `qty > 1` y un unitario de más de 2 decimales, los dos órdenes
de redondeo divergen y el total de la MF puede ser inalcanzable para Odoo (y
viceversa). Las alternativas evaluadas:

- **A. Redondear el unitario a 2 decimales en el PdV** — Odoo pasa a
  *redondear → multiplicar* igual que la MF; parten del mismo número y cuadran
  siempre, conservando la cantidad real en el ticket. Coste: el importe cobrado
  cambia en céntimos en toda venta. **Elegida.**
- **B. Enviar la línea a la MF como `qty = 1` con el total de línea** — cuadra
  en una línea sin tocar Odoo, pero el ticket fiscal mostraría `1 × total`
  (pierde la cantidad real → riesgo SENIAT) y con varias líneas vuelve a
  descuadrar por el redondeo línea-vs-total de Odoo. Descartada.
- **C. Flag 21 = 01 (3 decimales)** — cuadra en este caso pero no siempre, y
  baja el máximo por ítem a `9.999.999,999` Bs (riesgo de overflow con precios
  altos); es config de máquina. Descartada.

La A es la única que **garantiza estructuralmente** la paridad Odoo == MF
manteniendo la cantidad real, porque hace que ambos calculen desde el mismo
unitario de 2 decimales.

## Punto de intercepción: `setUnitPrice`

Es el único método por el que se fija el precio unitario de una línea
(aplicación de tarifa al agregar producto y edición manual de precio). Ya
estaba overrideado en `l10n_ve_pos` para derivar `foreign_price`. Se redondea
`this.price_unit` **después** de `super.setUnitPrice(...)` (para que el core
haya fijado el precio de la tarifa) y **antes** de derivar `foreign_price`
(para que el foráneo salga del local ya redondeado). Cambiar la cantidad no
pasa por aquí, así que el valor redondeado persiste.

## Qué moneda se usa para redondear

Se redondea a la moneda **en la que está expresado `price_unit`**, que es la
moneda de la orden:

- Orden en moneda principal (VE normal, Bs) → `order.roundLocalMoney()`
  (`_roundWithCurrency(_getMainCurrency())`, `decimal_places` = 2).
- Orden en moneda foránea (`_is_order_in_foreign_currency()`, escenario borde
  no usado en este stack porque la compañía es VEF) → `order.roundForeignMoney()`.

Se guarda con `if (order && typeof order.roundLocalMoney === "function")`:
si `setUnitPrice` corriera antes de que la orden esté lista, no se redondea y
se conserva el comportamiento actual (fallo hacia el lado seguro).

## Por qué NO rompe moneda foránea ni IGTF

- **Foránea**: el diseño ya fija que el local es primario y el foráneo se
  deriva con una sola conversión `localToForeign()` (ver comentario de
  `roundForeignMoney`: "NOT for unit prices"). Redondear el local sólo cambia
  el número de entrada de esa conversión; la invariante
  `Σ(get_foreign_price_*) == get_foreign_total_with_tax()` se mantiene y el $
  mostrado no se mueve de forma perceptible.
- **IGTF** (`l10n_ve_pos_igtf/.../order_model.js`): el IGTF se calcula sobre el
  local (`get_total_without_igtf() = totalDue`, `compute_igtf_amount = round(
  base × igtf_percentage/100)` con `res.currency.round`) y el lado foráneo es
  una única conversión del local, con nota explícita de que NO se calcula en
  paralelo en $. Todo se recalcula consistente sobre la nueva base.

## Desviación consciente de una convención existente

`pos_order.js::roundForeignMoney` documenta: *"Use for subtotals, taxes,
totals, due, change, payment amounts. **NOT for unit prices**"* — los precios
unitarios conservan la precisión del catálogo a propósito. Este change
**rompe** esa regla para el unitario local, priorizando la paridad con la
máquina fiscal. Queda anotado en el comentario del código y aquí.

## Verificación aritmética (orden 199 / factura 00004961)

| | antes | después |
|---|---|---|
| `price_unit` | 5068,865205 | 5068,87 |
| base Odoo (`amount_total`) | 20.275,46 | 20.275,48 |
| base MF (`5068,87 × 4`) | 20.275,48 | 20.275,48 |
| IGTF 3% | Odoo 608,26 / MF 608,26 | 608,26 |
| total con IGTF | Odoo 20.883,72 / MF 20.883,74 | 20.883,74 |
| cierre 199 | **NAK** (faltan 0,02) | **ACK** |
