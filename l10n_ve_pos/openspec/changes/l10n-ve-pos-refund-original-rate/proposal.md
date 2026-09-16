# Fix: código muerto en orderline.js + reembolsos convertían a divisa con la tasa de hoy, no la de la venta original (l10n_ve_pos)

## Why

Al revisar el bug documentado en `l10n-ve-pos-refund-full-button` (referencia
a `this.pos.toRefundLines`, inexistente en Odoo 19), se investigó a fondo
`static/src/overrides/components/orderline/orderline.js` y se encontró que
**todo el bloque `patch(Orderline.prototype, {...})` estaba muerto**, con
varias referencias rotas independientes entre sí, no solo la reportada:

- `this.pos` y `this.order` — nunca se definen en el componente `Orderline`
  de Odoo 19 (core no llama `usePos()` en su `setup()`; el override tampoco
  lo agregaba). El componente solo expone `this.props`/`this.line`.
- `this.order._isRefundOrder()` — este método no existe en ningún sitio, ni
  en el core de Odoo 19 ni en `l10n_ve_pos`. La API real en v19 es un
  getter: `order.isRefund` (`pos_order.js:196` del core).
- `this.foreign_currency_rate` — debía ser `this.line.foreign_currency_rate`
  (campo real, `related="order_id.foreign_currency_rate"`).
- `this.pos.toRefundLines` (el bug original reportado) — no existe; y
  además no hacía falta esa estructura: la línea original ya está
  disponible directamente vía `this.line.refunded_orderline_id` (relación
  many2one real, usada correctamente en `payment_screen.js:186`).
- `getDisplayData()` — hacía `super.getDisplayData(...)`, pero el
  `Orderline` de Odoo 19 core no tiene ese método (no existe en ningún
  archivo de `point_of_sale`). Si se hubiera invocado, habría lanzado
  `TypeError`.

Se confirmó por grep en todo el módulo (XML y JS) que **ninguno** de estos
métodos (`get_rate`, `currency_rate_display`, `get_refund_orderline`,
`getDisplayData`, y también los wrappers `get_foreign_price_*` que solo
delegaban al modelo) se invocaba desde ningún lado — el template real
(`orderline.xml`) siempre llamó directamente `line.get_foreign_price_with_tax()`
(el modelo `pos.order.line`, vía `pos_order_line.js`), no el componente.
Por eso nunca truena en producción, pero tampoco hacía nada.

Investigando el propósito original (git history hasta el commit
`2ba5ad91c [WIP]Agregando pos`, Odoo 17): este código vivía en
`orderline_model.js`, parcheando el **modelo** de datos `Orderline` de v17
(donde `this.pos`/`this.order` sí existían), y cumplía dos funciones reales
que se perdieron en la migración a v19 sin ser reimplementadas en ningún
otro lugar:

1. Al reembolsar, mostrar/convertir el monto en divisa de la línea con la
   tasa BCV de la venta ORIGINAL, no la tasa vigente al momento del
   reembolso.
2. El badge "(G)"/"(E)" (gravado/exento) junto al nombre del producto.

Se verificó además que el problema (1) es real HOY, más allá del código
muerto: `_getPosConversionRate()` en `pos_order.js` siempre lee
`pos.config.foreign_rate`/`foreign_inverse_rate` — un valor **vivo y
compartido** por toda la sesión, sin importar cuándo se creó la orden que
se está mostrando. El campo `foreign_currency_rate` guardado por orden
(`pos_order.py`, poblado una vez al sincronizar) existe en la base de
datos pero la UI en vivo no lo consultaba (solo aparecía como último
fallback en `get_display_rate()`).

## What Changes

- **Se elimina** `static/src/overrides/components/orderline/orderline.js`
  por completo (código 100% muerto, verificado por grep en todo el
  módulo).
- **`static/src/overrides/models/pos_order_line.js`** (donde ya vive toda
  la lógica activa de conversión foránea):
  - Nuevo `_refundOriginalRate()`: si la línea tiene
    `refunded_orderline_id` (es una línea de reembolso), devuelve el
    `foreign_currency_rate` congelado de la orden ORIGINAL
    (`refunded_orderline_id.order_id.foreign_currency_rate`) en vez de
    `null`. Si no es una línea de reembolso, o la orden original no tiene
    tasa congelada válida, devuelve `null` (comportamiento actual sin
    cambios).
  - `_get_raw_foreign_unit_price()` y `_localToForeignMoney()`: cuando
    `_refundOriginalRate()` devuelve una tasa, multiplican por esa tasa en
    vez de llamar a `order.localToForeign()` (que siempre usa la tasa
    viva). El redondeo final sigue pasando por
    `order.roundForeignMoney()`/`round_di` como antes, para no romper la
    regla de redondeo documentada en la cabecera del archivo.
  - Nuevo `get_aliquot_type()`: reimplementado usando `this.tax_ids` /
    `this.product_id.taxes_id` directamente (son objetos reales de
    `account.tax` en el related_models de v19, no ids — se confirmó
    contra `taxGroupLabels` del core, que hace lo mismo), sin depender de
    `this.pos.taxes_by_id` (inexistente en el modelo).
- **`static/src/overrides/components/orderline/orderline.xml`**:
  `line.aliquot_type` (propiedad inexistente, siempre `undefined`) →
  `line.get_aliquot_type()` (método real del modelo).

### Hotfix HI.1 (encontrado al verificar en navegador, 2026-07-20)

El fix inicial (solo en `pos_order_line.js`) no era suficiente: el total
que realmente se ve en la pantalla de pago (`foreignTotalDueText` en
`payment_screen.js`, que llama a `pos.order.get_foreign_total_with_tax()`
en `pos_order.js`) seguía usando la tasa viva, porque ese método convierte
el TOTAL agregado de la orden (`this.localToForeign(this._localTotalWithTax())`)
en vez de sumar los montos ya corregidos por línea. Verificado en vivo con
la orden 8016 (INV/2026/0028): -14.220,00 Bs mostraba $-19,29 (tasa de
hoy, 0,001356424930) en vez de $-20,32 (tasa original de la venta,
0,001428112596).

- **`static/src/overrides/models/pos_order.js`**: nuevo `_hasRefundLines()`
  y `_sumForeignLines(getterName)`. `get_foreign_total_with_tax()`,
  `get_foreign_total_without_tax()` y `get_foreign_total_tax()` ahora, si
  la orden tiene líneas de reembolso, suman los montos ya corregidos de
  cada línea (`line.get_foreign_price_with_tax()`, etc.) en vez de
  convertir el total agregado con la tasa viva de la orden. Esto también
  cubre correctamente el caso borde de una orden de reembolso que mezcla
  líneas de más de una orden original (mismo partner, destino reutilizado
  entre dos acciones de reembolso), cada una con su propia tasa congelada.
- Nuevo `_convertOrderAmount(amount)`: para `get_foreign_due()` y
  `get_foreign_change()` (montos que no se pueden sumar directamente por
  línea, son estado de pago), deriva la tasa efectiva realmente usada en
  el total (`foreign_total / local_total`) y la aplica al monto pedido, en
  vez de usar la tasa viva. Se usa el mismo método para ambos.

## Impact

- **Capability**: `pos-refund-original-rate` (nueva).
- **Módulo**: `l10n_ve_pos`, solo frontend
  (`static/src/overrides/models/pos_order_line.js`,
  `static/src/overrides/components/orderline/`). No toca modelos Python ni
  requiere `-u`, solo recarga de assets del PdV.
- **Cambio de comportamiento visible**:
  - El badge "(G)"/"(E)" ahora se muestra junto al nombre del producto en
    cada línea (antes nunca aparecía).
  - El monto en divisa de una línea de reembolso ahora se calcula con la
    tasa BCV de la venta original, no la del día del reembolso. Esto
    puede cambiar el monto en USD mostrado/convertido en reembolsos de
    órdenes creadas en una tasa distinta a la actual (el monto en
    bolívares reembolsado NO cambia, solo su equivalente en USD
    mostrado).
- **Riesgo de despliegue**: bajo — fallback a comportamiento anterior
  (tasa viva) si la orden original no tiene `foreign_currency_rate`
  poblado (p. ej. datos legados). Nada de lo eliminado estaba en uso.
