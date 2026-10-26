# Fix: una orden ya sincronizada vista en el TicketScreen mostraba tasa/totales en divisa con la tasa VIVA, no la de la venta (l10n_ve_pos)

## Why

El change `l10n-ve-pos-refund-original-rate` hizo que las **líneas de
reembolso** y los **totales de una orden de reembolso** convirtieran a
divisa con la tasa congelada de la venta original
(`foreign_currency_rate`), no con la tasa viva de `pos.config`. Pero dejó
sin cubrir el caso simétrico más común: **abrir una orden de venta normal
ya sincronizada** (TicketScreen, panel derecho con "Reembolso total" y
"Reimprimir Documento Fiscal").

Ahí, el panel pinta:

```xml
<attribute name="conversion_rate">_selectedSyncedOrder.get_display_rate_formatted()</attribute>
<attribute name="foreign_total">...get_foreign_total_with_tax()...</attribute>
<attribute name="foreign_tax">...get_foreign_total_tax()...</attribute>
```

Y para una orden de venta vista (sin líneas de reembolso), el baseline
`origin/19.0` usa la tasa **viva**, no la de la orden:

1. `get_display_rate()` prueba primero `pos.config.foreign_inverse_rate`
   (viva); la congelada `order.foreign_currency_rate` era solo el ÚLTIMO
   fallback → gana la viva. (La propia proposal de
   `l10n-ve-pos-refund-original-rate` ya notaba esto.)
2. `get_foreign_total_with_tax()` / `_without_tax()` / `_tax()` solo usan la
   tasa congelada cuando la orden `_hasRefundLines()`. Una venta original
   vista no tiene líneas de reembolso → reconvierte los totales a la tasa
   VIVA (`order.localToForeign`).
3. El monto foráneo por línea (`pos_order_line.js::_localToForeignMoney`)
   usa la congelada solo si la línea tiene `refunded_orderline_id`. Las
   líneas de una venta vista → tasa viva.

Como la tasa BCV cambia a diario, una venta de otro día se muestra con una
tasa y unos totales en divisa que NO son los que efectivamente se cobraron.
La tasa congelada ya está cargada en el cliente
(`pos_order.py::_load_pos_data_read` inyecta `foreign_currency_rate`), solo
que no se priorizaba.

## What Changes

- **`static/src/overrides/models/pos_order.js`** — motor de conversión
  unificado (rate-explícito):
  - `_convertAtRate(from, rate, toCurrency, doRound)`: gemelo rate-explícito
    de `_convert` (mismo `from * rate` + mismo redondeo con la moneda
    destino), pero con la tasa pasada en vez de buscada en `pos.config`.
  - `localToForeignAtRate(amount, mainToForeignRate)` /
    `foreignToLocalAtRate(amount, foreignToLocalRate)`: gemelos de
    `localToForeign` / `foreignToLocal` para tasa histórica. **Todas** las
    conversiones a tasa no-viva (congelada de la venta, tasa exacta del pago
    original, proporción de reembolso) pasan ahora por estas primitivas —
    se eliminó el `* tasa` / `/ tasa` inline que había en
    `_convertOrderAmount`, `_convertForeignOrderAmount`, `_frozenLocalToForeign`,
    `pos_order_line.js::_localToForeignMoney`/`_get_raw_foreign_unit_price` y
    la rama exacta de `payment_model.js`. Así todo el dinero comparte un solo
    multiplicar + un solo redondear, igual que el par vivo.
  - `_frozenOrderMultiplier()` / `_isFrozenRateOrder()` /
    `_frozenLocalToForeign()`: helpers que exponen la tasa congelada
    (`foreign_currency_rate`) de una orden **finalizada** (`this.finalized`);
    `_frozenLocalToForeign` delega en `localToForeignAtRate`.
  - `get_foreign_total_with_tax()` / `_without_tax()` / `_tax()`: cuando la
    orden es una venta finalizada (no reembolso), convierten el total local
    con la tasa congelada en vez de la viva. El branch de reembolso
    (`_hasRefundLines`) se mantiene primero e intacto.
  - `get_display_rate()`: para una orden finalizada muestra la tasa que sus
    montos realmente usan (venta = su `foreign_currency_rate`; reembolso =
    tasa efectiva derivada de los totales, ya al día del original), de modo
    que la tasa mostrada siempre concuerda con los totales mostrados.
- **`static/src/overrides/models/pos_order_line.js`**:
  - `_localToForeignMoney()`: para las líneas de una orden finalizada (no
    reembolso) convierte con la tasa congelada de la orden, igual que los
    totales.

## Impact

- **Capability**: `pos-refund-original-rate` (extendida — mismo dominio de
  "usar la tasa de la orden, no la de hoy").
- **Módulo**: `l10n_ve_pos`, solo frontend. Fix **visual**; no toca cálculo
  contable ni el asiento. Requiere recarga de assets del PdV.
- **Gate `finalized`**: solo cambia la orden ya sincronizada que se
  reabre. La orden VIVA en construcción (venta de mostrador, pantalla de
  pago, impresión fiscal MF, IGTF en el pago) queda intacta usando la tasa
  viva — su `foreign_currency_rate` o no existe aún o es igual a la viva.
- **Cambio de comportamiento visible**: al ver/​reimprimir una orden pasada,
  la tasa y los totales en divisa pasan a reflejar la venta original, no la
  tasa de hoy. Es el mismo principio del ticket #15114.
- **Riesgo**: bajo — refactor aditivo y gateado; los consumidores de la
  orden viva caen al camino previo sin cambios.
