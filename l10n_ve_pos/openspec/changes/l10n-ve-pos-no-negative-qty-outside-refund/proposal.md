# Feature: prohibir cantidades negativas fuera de las líneas de reembolso (l10n_ve_pos)

## Why

Odoo 19 permite poner en negativo la cantidad de **cualquier** línea del
carrito del PdV. El camino más directo es la tecla `+/-` del numpad
(`SWITCHSIGN = { value: "-", text: "+/-" }` en
`point_of_sale/static/src/app/components/numpad/numpad.js:34`), que en
`OrderSummary.updateSelectedOrderline` convierte la cantidad actual en su
negativo, pero también sirve teclear directamente `-3`, o pulsar el botón
"−" hasta pasar de cero.

El resultado es una orden de **venta** con una línea de cantidad negativa.
En Venezuela eso es un problema real y no solo cosmético: la orden se
factura como venta con cantidad negativa (y así llega a la impresora fiscal
vía `l10n_ve_pos_mf` y al Libro de Ventas) en vez de emitirse como la nota
de crédito que corresponde a una devolución. El core no lo impide porque
para Odoo una línea negativa es una forma válida de "descuento/devolución
rápida"; en VE no lo es.

El flujo correcto para devolver mercancía ya existe y debe seguir
funcionando sin cambios: `TicketScreen` → seleccionar la orden original →
`Refund`, que crea líneas con `refunded_orderline_id` apuntando a la línea
reembolsada (`point_of_sale/static/src/app/screens/ticket_screen/ticket_screen.js:342`).

## What Changes

### Frontend (PdV)

- `static/src/overrides/models/pos_order_line.js`: se añade al `patch` ya
  existente un override de `setQuantity(quantity, keep_price)` que devuelve
  el objeto de error `{title, body}` (contrato nativo de Odoo 19, ver
  abajo) cuando la cantidad resultante es **negativa** y la línea **no** es
  de reembolso. En cualquier otro caso delega en `super`.
- Se elige `setQuantity` como único punto de intercepción porque por ahí
  pasan **todos** los caminos de edición de cantidad del PdV: numpad
  (`OrderSummary._setValue`), `QuantityButtons`, código de barras con peso
  (`PosOrderline.setup` → `setQuantity(code.value)`), `setQuantityByLot` y
  la propagación a las líneas hijas de un combo.
- Contrato aprovechado: en Odoo 19 `setQuantity` devuelve `true` si tuvo
  éxito o un `{title, body}` que `OrderSummary._setValue`
  (`order_summary.js:249`) renderiza como `AlertDialog` y seguido resetea
  el `number_buffer`. Es el mismo mecanismo que usa el core para
  "Positive quantity not allowed" en líneas de reembolso, así que la UX del
  mensaje es idéntica a la nativa, sin componentes nuevos.
- Se importa `parseFloat` de `@web/views/fields/parsers` **con alias**
  (`parseFloatLocale`). El resto del fichero usa el `parseFloat` global
  sobre cadenas de `toFixed()` (siempre con punto decimal); el parser de
  `@web` es sensible al locale (coma decimal en es_VE) y rompería esas
  llamadas si sombreara al global.

### Backend

- `models/pos_order_line.py`: `@api.constrains("qty",
  "refunded_orderline_id", "order_id")` que levanta `ValidationError` bajo
  las mismas condiciones. El guard de JS es la primera línea de defensa
  (mensaje claro, sin romper la sesión), pero el sync del PdV y el backend
  escriben `qty` directamente por RPC, así que sin la constraint la regla
  no queda realmente impuesta. Se compara con `float_compare` a la
  precisión decimal `Product Unit` para no disparar por ruido de redondeo.

### Exenciones (idénticas en frontend y backend)

1. `refunded_orderline_id` presente → línea de reembolso real.
2. `order_id.is_refund` (solo backend) → orden marcada como reembolso por
   el core; cubre líneas hijas de combo y cualquier línea que el core
   añada a una orden de reembolso.
3. `order_id.preset_id.is_return` → preset nativo "Return mode"
   (`point_of_sale/models/pos_preset.py:16`), donde el propio core fuerza
   `-Math.abs(qty)` en `PosOrder.setPreset` y crea las líneas con `qty: -1`
   en `PosStore.addLineToOrder`. Bloquearlo dejaría ese modo roto **en
   silencio**, porque ambos llamantes ignoran el valor de retorno de
   `setQuantity`.

Nótese que el guard **no** afecta a la creación de líneas de reembolso:
`onDoRefund` las crea directamente con
`models["pos.order.line"].create({qty: -refundDetail.qty, ...})`, sin pasar
por `setQuantity`.

### Traducciones

- `i18n/es_VE.po`: se añaden las tres cadenas nuevas (una de Python, dos de
  JS) con su traducción al español. Los `msgid` van en inglés siguiendo la
  convención del proyecto (Odoo traduce vía `.po` desde el string fuente en
  inglés).

## Impact

- **Capability**: `pos-negative-qty-guard` (nueva).
- **Módulo**: `l10n_ve_pos`. Toca frontend
  (`static/src/overrides/models/pos_order_line.js`), Python
  (`models/pos_order_line.py`) e `i18n/es_VE.po`. Requiere `-u l10n_ve_pos`
  para que se carguen la constraint nueva y las traducciones; solo recargar
  assets basta para el guard de JS pero deja el mensaje en inglés.
- **Riesgo de despliegue**: bajo-medio. El guard de JS es aditivo y falla
  "hacia el lado seguro" (la cantidad simplemente no cambia). El riesgo
  real está en la constraint: si alguna orden legítima llegara a sincronizar
  con línea negativa fuera de las tres exenciones, el sync fallaría con
  `ValidationError` y la orden quedaría atascada en el navegador. Se
  auditaron todos los caminos que crean `qty` negativo en `point_of_sale`,
  `enterprise` y `odoo-venezuela` y los únicos son
  `pos.order.line._prepare_refund_data` (`'qty': -(self.qty -
  self.refunded_qty)`, exento por `refunded_orderline_id`), `onDoRefund`
  (exento igual) y el preset `is_return` (exento). `l10n_ve_pos_igtf` solo
  toca pagos y `l10n_ve_pos_mf` ya normaliza con `Math.abs(...)` antes de
  enviar a la impresora fiscal.
- **Datos históricos**: `@api.constrains` solo se evalúa en `create`/`write`
  de los campos vigilados, así que las órdenes negativas ya existentes en
  base de datos no se tocan ni bloquean el upgrade del módulo. Sí fallarían
  si alguien reescribe su `qty` desde el backend, que es el comportamiento
  deseado.
- **Fuera de alcance**: `OrderSummary.handleDecreaseLine` crea una línea
  negativa a propósito para reducir una línea ya enviada
  (`order_summary.js:334`). Ese camino solo se alcanza cuando
  `pos.disallowLineQuantityChange()` es verdadero, cosa que en este stack
  nunca ocurre (el core devuelve `false` y solo lo sobreescriben los
  módulos fiscales `l10n_de_pos_res_cert`, `l10n_se_pos` y
  `pos_blackbox_be`, ninguno instalado en VE). Si alguna vez se instalara
  uno, ese flujo quedaría bloqueado por el guard y habría que exentarlo
  explícitamente.
- **Descuentos negativos**: el guard cubre solo la **cantidad**. Un precio
  unitario o un descuento negativo siguen siendo posibles desde el numpad
  (`numpadMode === "price"` / `"discount"`); no estaba en el alcance
  pedido y se deja documentado por si se quiere abordar aparte.
- **Comportamiento nativo confundible con este guard** (visto durante la
  verificación, no es un fallo): al intentar agregar un producto a una
  orden de reembolso sale el diálogo "Uy" / "Asegúrese de validar el
  reembolso antes de tomar otro pedido". Es
  `PosStore.addLineToOrder` (`pos_store.js:898`) vía
  `PosOrder.isSaleDisallowed` (`pos_order.js:437`:
  `this.isRefund && (!values.qty || values.qty > 0)`), sin relación con
  este change. Conviene saber que **`is_refund` es pegajoso**: se fija una
  sola vez en `ticket_screen.js:328` y nunca se limpia, así que borrar
  todas las líneas del reembolso no "devuelve" la orden a estado de venta
  — hay que abrir una orden nueva.
