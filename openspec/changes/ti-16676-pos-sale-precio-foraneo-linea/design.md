# Diseño: precio alterno de las líneas del PdV liquidadas desde una orden de venta

## Context

La motivación está en proposal.md (Why). Aquí va solo lo que define el enfoque.

**Dónde nace `foreign_price` en el PdV.** Solo en el patch de `l10n_ve_pos` sobre `PosOrderline.setUnitPrice`
(`static/src/overrides/models/pos_order_line.js`). El core llega ahí por `setOptions()`, que llama a
`setUnitPrice(this.price_unit)` en `PosStore.addLineToOrder`, y por `PosOrder.setPricelist`. Desde
`534aaac9114d`, `pos_sale` sobrescribe `setUnitPrice`: con `sale_order_line_id` asigna `price_unit` sin `super`.
El core de GitHub (`~/odoo`, 19.0 al 2026-11-24) sigue igual que la imagen instalada.

Líneas que hoy se sincronizan sin precio alterno, según `pos_sale/static/src/app/services/pos_store.js` y el core:

| Camino | Por qué queda en 0 |
|---|---|
| Líneas de la orden de venta (`settleSO`: `addLineToCurrentOrder` + `setUnitPrice(converted_line.price_unit)`) | llevan `sale_order_line_id`, así que `pos_sale` salta a `l10n_ve_pos` |
| Líneas partidas por UoM no agrupable o por lote (`models["pos.order.line"].create({...newLineValues})`) | mismo motivo; la última rama de lotes ni siquiera llama a `setUnitPrice` |
| Anticipos de la orden de venta (`is_downpayment` en la línea de venta) | llevan `sale_order_line_id` |
| Anticipo por la diferencia ya pagada (`addDownPaymentProductOrderlineToOrder(sale_order, -paidDiff)`) | pasa por `l10n_ve_pos`, pero con precio negativo `_get_raw_foreign_unit_price` devuelve 0 (el defecto que #1649 corrige en el JS) |
| Hijas de combo (`combo_line_ids: [["create", {price_unit}]]`) | el core las crea sin `setUnitPrice`. **No verificado con datos**: no hay combos en las bases locales |
| Reembolso desde el PdV (`onDoRefund`) | ya cubierto por el #15106 (copia el precio alterno de la línea original) |

**Servidor.** `sync_from_ui` llama a `_process_order`:

- Orden nueva: `pos.order.create` con `[0, 0, vals]`, que termina en `pos.order.line.create`. El core llama a
  `_complete_values_from_session` en `pos.order.create`, así que la cabecera ya trae `foreign_currency_rate`
  cuando se crean las líneas.
- Borrador ya sincronizado: primero `pos_order.write({"lines": cmds})`. Las líneas modificadas llegan como
  `[1, id, vals]` con **todos** sus campos (`deepSerialization` del PdV), un `[0, 0, vals]` con un uuid que ya
  existe se convierte en `[1, id, vals]`, y las borradas llegan como `[2, id]`/`[3, id]`. Después
  `pos_order.write(order)` actualiza la cabecera, incluida la tasa. La factura sale al final, en
  `_process_saved_order`.
- El PdV sincroniza borradores al abrir la pantalla de órdenes (`getServerOrders`, que llama a
  `syncAllOrders`), al programar un preset, al imprimir en cocina y al cerrar con órdenes abiertas. Tras cada
  sincronización recarga las líneas del servidor (`loadConnectedData`), con `foreign_price` incluido
  (`_load_pos_data_fields`).
- `_get_invoice_lines_values` copia `foreign_price` a la línea contable. `l10n_ve_accountant` lo respeta (no lo
  recalcula al publicar), deriva de ahí `foreign_subtotal` y los alternos del IVA, y arma la CxC como la suma
  de las demás líneas.

**Precisión del lado del PdV.** `_foreignUnitPriceDp()` lee el `decimal.precision` llamado
"Foreign Product Price" (`l10n_ve_accountant.alternative_price_product`, noupdate, 6 por defecto; 2 en
`posconsultoria_ti16585`; en la rama `19.0`, `l10n_ve_pos_mf` lo fija en 2 por el ticket 16356). Si no lo
encuentra, usa los decimales de la moneda alterna. Redondea con `roundDecimals`, que es HALF-UP, igual que
`float_round`.

**Ramas.** Este cambio parte de `19.0`. `pos_order_line.py` y `pos_order_line.js` eran idénticos en `maintenance-19.0`, `19.0` y el checkout
de posconsultoria (f9adcae31). En `pos_order.py`, `19.0` agrega solo la moneda de cobro
(`_set_payment_tender_values`, `get_refund_tender_rates`). `_get_payment_foreign_rate` y
`_get_invoice_lines_values` son iguales en las tres. El requirement "La factura del PdV hereda la tasa de la
orden" también es idéntico en las tres specs. Versiones de `l10n_ve_pos`: maintenance 19.0.1.28.1, 19.0
19.0.1.30.0, checkout 19.0.1.32.0. El PR abierto odoo-venezuela#1649 (ticket 16547, base
`maintenance-19.0`, 19.0.1.28.2) agrega `write` y `_sync_global_discount_foreign_price` en `pos.order.line`,
con la misma fórmula: `price_unit × order._get_payment_foreign_rate()` y la precisión "Foreign Product Price".

## Goals / Non-Goals

**Goals:**

- Que toda línea del PdV guardada con precio distinto de cero tenga precio alterno, por cualquier camino del
  JS y con cualquier orden de carga de los patches.
- Una sola fórmula en el servidor, compartida por el backfill, la factura y el descuento global de #1649.

**Non-Goals:**

- Tocar el JS (D6).
- Reparar las facturas ya publicadas (ver "Datos ya afectados").
- Usar el precio alterno de la línea de la orden de venta. Se usa la tasa de la caja, como antes de la
  regresión y como la cabecera de la factura.
- Problemas del core sin efecto en el alterno: la rama de lotes que no llama a `setUnitPrice` deja el precio
  de la línea de venta sin convertir si la orden de venta está en otra moneda.

## Decisions

**D1. Se corrige en el servidor, de forma genérica, en `pos.order.line.create`/`write`.** Se descarta, primero,
un patch JS cargado después de `pos_sale`: necesita un módulo que dependa de `pos_sale` (D6), deja abiertos los
demás caminos (anticipos negativos, combos, el próximo cambio del core) y no corrige la factura de una línea ya
guardada. También se descarta un gancho único en `pos.order._process_saved_order`. Ahí la tasa ya es la final,
pero no ve el cambio de precio de una actualización (D4) ni las líneas creadas fuera de la sincronización, como
el reembolso del backend o las pruebas. Por último, se descarta recalcular siempre todas las líneas: pisaría el
precio congelado de los reembolsos (#15106) y el que el PdV ya mandó bien. Hacerlo en `create`/`write` sigue el
precedente de #15106 y de #1649.

**D2. Fórmula: un helper, `pos.order.line._get_foreign_price_from_price_unit()`.**

- Caja en la moneda alterna (`order.currency_id == order.config_id.foreign_currency_id`, el equivalente de
  `_is_order_in_foreign_currency` del JS): devuelve el precio unitario redondeado. Con la tasa 1 que manda el
  PdV en ese caso daría lo mismo, pero se deja explícito para no depender de la tasa guardada.
- Si no: `price_unit × order._get_payment_foreign_rate()`. Es la tasa del PdV estampada en la orden
  (`pos.order.foreign_currency_rate`, que el PdV fija al sincronizar con `init_conversion_rate` →
  `get_foreign_multiplier()`, desde `pos.config.foreign_rate`) o, en un reembolso, la de la venta original.
  **No es la tasa de la orden de venta (`sale.order`) ni la del día (`res.currency.rate`).** Es la misma que usan
  #1649 y los pagos, y coincide con la cabecera de la factura (`_get_move_foreign_rate_vals(self.foreign_currency_rate)`).
- **Tasa por línea, alineada con el JS:** la línea que reembolsa otra (`refunded_orderline_id`) usa la tasa de
  la orden original (`_refundOriginalRate`); la línea de descuento global usa `_get_payment_foreign_rate()`
  (conserva #1649); cualquier otra, incluida una línea nueva en una orden de reembolso (cambio de producto), usa
  la tasa de su propia orden.
- **Recursión:** un alterno calculado en 0 (redondeo) es válido. `_write_foreign_price` solo escribe si el valor
  cambia y con el contexto `l10n_ve_pos_skip_foreign_fill`, con el que `write` no reaplica las reglas A/B.
- **Desviación en la implementación:** la rama "caja alterna" solo aplica si la orden no trae tasa. Una caja
  alterna estampa tasa 1 (mismo resultado) y el fixture de pruebas tiene el diario en VEF con tasa 36,5, donde
  la rama por moneda daría el precio sin convertir.
- Redondeo: `float_round(..., precision_digits=precision_get("Foreign Product Price"))`, HALF-UP. El respaldo
  del JS (decimales de la moneda) no aplica en el servidor: el registro siempre existe con
  `l10n_ve_accountant`.
- Conserva el signo. Esto **cambia lo propuesto** ("replicar exactamente el JS"): el JS de `maintenance-19.0`
  devuelve 0 con precio negativo, y replicarlo dejaría en 0 los anticipos descontados. Va en línea con #1649,
  que corrige eso en el JS.
- Sin tasa devuelve `None` y la línea queda como llegó.

**D3. Orden de las reglas.** Un helper `_fill_missing_foreign_price()` se aplica a las líneas con
`foreign_price` en 0 y precio distinto de cero. Primero copia el precio alterno de `refunded_orderline_id` (la
regla del #15106, que hoy está inline en `create` y se mueve aquí sin cambiar su efecto). Si sigue en 0, lo
calcula con D2. `create` lo llama al final, en lugar del bucle actual, y después de
`_sync_global_discount_foreign_price` si #1649 ya está. **Cambio respecto a lo propuesto:** un reembolso cuya original también
está en 0 (datos dañados por este bug) ya no queda en 0. Se calcula a la tasa de la venta original, y así la NC
cuadra por sí sola. Eso invierte dos pruebas del #15106 (ver Risks).

**D4. Ruta `write`.** Dos reglas, ambas después de `super().write(vals)` y solo si `price_unit` o
`foreign_price` vienen en `vals`:

- **Regla A:** `_fill_missing_foreign_price()` sobre las líneas escritas. Cubre una actualización que trae
  `foreign_price` en 0.
- **Regla B:** si `price_unit` viene en `vals`, antes de `super` se toman las líneas cuyo precio cambia (según la
  precisión "Product Price") y cuyo `foreign_price` no cambia (no viene en `vals` o viene igual al guardado,
  según la precisión "Foreign Product Price"). Después de `super` se recalculan con D2. Es el caso real de este
  bug en la ruta `write`. El PdV recarga del servidor el valor completado en la primera sincronización (D1), y si
  el cajero luego edita el precio de una línea de la orden de venta, `pos_sale` cambia `price_unit` sin tocar
  `foreign_price`. La siguiente sincronización manda el precio nuevo con el alterno viejo. Una línea normal no
  dispara la regla: `l10n_ve_pos` recalcula `foreign_price` cuando cambia el precio. Si el cambio de precio no
  alcanza a mover el alterno redondeado, recalcular da el mismo valor.
- La regla B también cubre la línea [DISC] cuyo precio reasigna `pos_discount`, que #1649 recalcula siempre:
  las dos reglas se solapan sin conflicto. Con el kiosko, `recompute_prices` reescribe `price_unit` y la regla B
  recalcula, pero `l10n_ve_pos_self_order` vuelve a escribir enseguida su `config._convert`, así que su
  resultado final no cambia.
- Las escrituras de `foreign_price` dentro del override vuelven a entrar a `write` con
  `vals = {"foreign_price": x}`. Con x ≠ 0 no se dispara nada, así que no hay recursión. Conviene agrupar las
  líneas por valor y escribir una vez por grupo.

**D5. Red de seguridad en `pos.order._get_invoice_lines_values`.** Después de la regla de reembolso que ya
existe, si `foreign_price` sigue en 0, el precio de la línea no es cero y el valor devuelto es una línea de
producto (no la sección de un combo), se usa `pos_order_line._get_foreign_price_from_price_unit()`. No se
escribe en la línea de orden: la factura no debe tener efectos laterales. Cubre las órdenes sincronizadas antes
del cambio que se facturan después (desde el backend o al cerrar) y cualquier camino que se escape de D3/D4.

**D6. El frontend queda fuera del alcance.** Ningún consumidor del PdV depende del `foreign_price` guardado en el
navegador:

- Pantalla, recibo, totales y ticket screen usan `get_foreign_price_*`, que convierten los precios locales del
  core con `localToForeign` o con la tasa congelada.
- La máquina fiscal (`l10n_ve_pos_mf`, `PosStore.js`) usa `price_unit` si la moneda base es VEF/VES. Si no, usa
  `get_foreign_unit_price()`, que recalcula al vuelo cuando el valor guardado es 0.
- El reembolso desde el PdV calcula en el JS con la tasa de la original, y el servidor copia el `foreign_price`
  de la original, que con este cambio ya está bien.
- Después de sincronizar, el navegador recibe del servidor el valor completado.

Si se quisiera de todos modos, el patch tendría que cargarse después del de `pos_sale`. Hay dos formas:

- En `l10n_ve_pos_sale` (depende de `l10n_ve_sale`, `l10n_ve_pos` y `pos_sale`; hoy es solo el puente de
  `sale.report`, no es `auto_install` y no está instalado en posconsultoria). Habría que marcarlo `auto_install`
  y declarar assets en `point_of_sale._assets_pos`, con un `setUnitPrice` que llame a `super` (el de `pos_sale`)
  y después a un helper de `l10n_ve_pos`.
- En `l10n_ve_pos`, sin dependencia: completar los ceros en `PosOrder.serializeForORM`. Es un parche menos
  limpio.

**D7. Coordinación con #1649 / #1662.** Los dos tocan `create`, `write` y la fórmula. El fix del descuento global
(ticket 16547) llega a `19.0` por el PR #1662; esta rama está apilada sobre la suya porque este fix extiende su código. Su `_sync_global_discount_foreign_price` pasa a llamar al helper de D2 en
vez de repetir `float_round(price_unit × rate)`. Su prueba de "precio alterno desfasado sin cambio de precio"
sigue cubierta por #1649: este cambio no recalcula un precio alterno distinto de cero si el precio no cambió.

**D8. Pruebas.**

- Python en `l10n_ve_pos`, archivo nuevo `tests/test_pos_line_foreign_price_backfill.py`, sobre
  `TestPosSessionAccountingBase` (USD base, VEF alterna, tasa 36,5), con `_create_rate_of_day` para la factura.
- El caso `pos_sale` real va en el mismo módulo con `SkipTest` si `sale_order_line_id` no está en los campos de
  `pos.order.line`. Es el patrón de #1649 con `pos_discount`: la lógica es de `l10n_ve_pos`, y en una base con
  `pos_sale` (como posconsultoria) la prueba corre. La alternativa es `l10n_ve_pos_sale/tests`, pero ese módulo
  no es `auto_install` y solo correría donde esté instalado.
- La regresión del JS (`settleSO` real) necesitaría un tour. No se propone porque el JS no cambia.

**D9. Versión.** Las correcciones recientes de `l10n_ve_pos` suben el manifest (#15106: 1.12 → 1.13). En la rama
`19.0` se sube de 19.0.1.30.1 (la del #1662) a **19.0.1.30.2**. No hay migración.

## Risks / Trade-offs

- **[Tasa cambiada entre dos sincronizaciones de un borrador]** El core escribe las líneas antes que la
  cabecera, así que una línea completada en la segunda sincronización toma la tasa guardada en la primera. →
  Solo pasa si la caja recargó una tasa distinta con la orden abierta. En el checkout de posconsultoria la
  sesión trabaja con la tasa de su apertura (ticket 16351). Se acepta y queda documentado.
- **[Precio alterno desfasado con el mismo precio]** No se detecta (D7). → Solo #1649 lo resuelve, y solo para
  [DISC].
- **[Líneas que estaban "legítimamente" en 0]** `test_non_refund_line_foreign_price_untouched` y
  `test_refund_line_no_backfill_when_original_has_no_foreign_price` (#15106) afirmaban que una línea con
  precio y sin alterno se quedaba en 0. No se encontró un caso de negocio que lo necesite. Pero un alterno en 0 no
  siempre es un error: con la precisión "Foreign Product Price" en 2 y 600 Bs/USD, una línea de 2 Bs da
  0,0033 y redondea a 0,00, que es válido. El código no debe reintentar ni recursar sobre ese 0: solo escribe
  si el valor cambia y las escrituras internas llevan el contexto `l10n_ve_pos_skip_foreign_fill`. → Se reescriben (tasks.md 1.6). La precondición del kiosko
  (`test_kiosk_order_line_foreign_price_filled_by_recompute`, `assertEqual(order.lines.foreign_price, 0.0)`) ya
  no se cumple al crear la orden. → Se fuerza el 0 por SQL o se quita la precondición (tasks.md 1.7).
- **[Orden de venta en la moneda alterna]** `read_converted` pasa el precio a Bs con la tasa de Odoo, y el
  servidor lo vuelve a USD con la de la caja. Si las dos tasas difieren, el alterno puede no ser exactamente
  el de la orden de venta. → Es lo mismo que hacía el JS antes de la regresión.
- **[Conflicto con #1649]** Los dos tocan los mismos métodos. → La rama va apilada sobre la del #1662, que se mergea primero (D7).
- **[Rendimiento]** Una escritura por línea en órdenes grandes. → Agrupar por valor (D4).
- **[Combos]** No se verificó si las hijas de combo llegan hoy con 0. Si llegan, este cambio también las
  corrige, y eso cambia el alterno de facturas de combos frente a hoy. → Verificarlo en el navegador
  (tasks.md 4.5).

## Migration Plan

- Despliegue: `-u l10n_ve_pos`. No cambia el esquema ni hay datos que migrar.
- Efecto inmediato: rige para las líneas que se creen o actualicen y para las facturas que se generen desde ese
  momento, incluidas las de órdenes ya sincronizadas que se facturen después (D5). Lo ya publicado no cambia.
- Reversión: revertir el módulo. Los precios alternos ya completados quedan, y son correctos.

## Datos ya afectados (decisión pendiente del usuario)

Fuera del alcance del fix. Para cada cliente con `pos_sale` instalado desde que tomó una imagen con
`534aaac9114d` (core, merge del 2026-10-16).

**Detectar las líneas del PdV en 0** (la columna `sale_order_line_id` existe solo con `pos_sale`):

```sql
SELECT po.id AS pos_order_id, po.name, po.date_order, po.state, po.foreign_currency_rate,
       pol.id AS line_id, pol.price_unit, pol.qty, pol.foreign_price,
       pol.sale_order_line_id, pol.refunded_orderline_id, pol.combo_parent_id,
       po.account_move
  FROM pos_order_line pol
  JOIN pos_order po ON po.id = pol.order_id
 WHERE COALESCE(pol.foreign_price, 0) = 0
   AND pol.price_unit <> 0
 ORDER BY po.date_order;
```

**Detectar facturas y NC afectadas:**

```sql
SELECT am.id, am.name, am.move_type, am.state, am.payment_state, am.date,
       po.id AS pos_order_id, ps.name AS session, ps.state AS session_state,
       po.foreign_amount_total,
       COUNT(aml.id) AS product_lines_in_zero
  FROM account_move am
  JOIN pos_order po ON po.account_move = am.id
  JOIN pos_session ps ON ps.id = po.session_id
  JOIN account_move_line aml ON aml.move_id = am.id
 WHERE aml.display_type = 'product'
   AND aml.price_unit <> 0
   AND COALESCE(aml.foreign_price, 0) = 0
 GROUP BY am.id, po.id, ps.id
 ORDER BY am.date;
```

**Enfoques de corrección:**

1. **Origen (sin efecto contable):** completar `pos_order_line.foreign_price` con el helper de D2 (script en
   `odoo shell` o `post-migrate` opcional). Deja bien los reembolsos futuros desde el PdV y la red de
   seguridad deja de ser necesaria para esas órdenes.
2. **Facturas publicadas, pasando a borrador:** borrador, `foreign_price` de las líneas de producto
   (l10n_ve_accountant recalcula subtotal, IVA y CxC en alterno) y volver a publicar. Riesgos:
   - Con la sesión abierta, `button_draft` está bloqueado salvo `pos_move_to_draft`, y desconciliar salvo
     `pos_unreconcile_moves`.
   - Con la sesión cerrada, la CxC ya está conciliada con los pagos del cierre: hay que desconciliar y
     volver a conciliar, y revisar si el descuadre generó asientos de diferencia en alterno
     (`l10n_ve_exchange_foreign_diff_entry`; no verificado) que haya que revertir.
   - Número fiscal o de control ya emitido por la máquina fiscal: hay que confirmar que volver a publicar
     no reimprima ni renumere.
   - Días de bloqueo fiscal (`l10n_ve_fiscal_lock_days`), periodos cerrados, libros ya declarados y la
     bitácora de auditoría.
3. **Facturas publicadas, script directo** sobre los campos alternos de las líneas (producto, IVA y CxC) sin
   pasar a borrador. Es más rápido y no toca la numeración, pero se salta las validaciones y obliga a
   recalcular a mano todo lo derivado (residuales y conciliaciones en alterno). Es el de más riesgo.

Recomendación: correr las consultas por cliente, corregir el origen (1) siempre y decidir 2 o 3 según el volumen
y el estado de las sesiones. Mientras la sesión siga abierta, lo menos costoso es corregir antes del cierre.

## Open Questions

- ¿Hay ticket propio para este bug, o va bajo el 16547/16585? Define el nombre de la rama y el enlace
  "Ticket:" del PR. No cambia el diseño.
- ¿En qué corre el CI del repo? ¿Instala `pos_sale` para las pruebas de `l10n_ve_pos`? Si no, la prueba con
  `SkipTest` (D8) se salta allí y conviene correrla a mano en una base con `pos_sale`.
