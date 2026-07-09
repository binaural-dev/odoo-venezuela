# Migration Lessons: l10n_ve_pos_igtf Odoo 17 → 19

## Hallazgos específicos de este módulo

### `this.pos` → `this.currency` / `this.config`

Archivo: `static/src/app/overrides/models/order_model.js`

En Odoo 19, el PosOrder NO tiene `this.pos` setteado. Reemplazar:

| Código O17 | Código O19 |
|-----------|------------|
| `this.pos.currency.rounding` | `this.currency.rounding` |
| `this.pos.config.igtf_percentage` | `this.config.igtf_percentage` |
| `this.pos.config.cash_rounding` | `this.config.cash_rounding` |

### `payment_method` → `payment_method_id`

Archivos: `order_model.js`, `payment_status.js`

Todas las referencias a `payment.payment_method` deben cambiarse a `payment.payment_method_id`. Además, como `payment_method_id` puede ser `undefined`, usar optional chaining: `payment.payment_method_id?.apply_igtf`.

### `formatCurrency` signature

Archivo: `payment_status.js`

En O19, `formatCurrency` y `formatForeignCurrency` aceptan solo 1 argumento (el valor). El segundo argumento `'Product Price'` que se usaba en O17 debe eliminarse.

### `payment_ids` en vez de `get_paymentlines()`

Archivos: `order_model.js`, `payment_status.js`

En O19, `payment_ids` es un getter (retorna array de pagos). No hay método `get_paymentlines()`. Se puede usar directamente:
```js
Array.from(this.payment_ids || [])
```
O agregar un wrapper en el patch:
```js
get_paymentlines() {
    return this.payment_ids ? Array.from(this.payment_ids) : [];
}
```

### XPath para PaymentScreenStatus

Archivo: `static/src/app/overrides/screens/payment_status.xml`

El template nativo O19 cambió. Las clases `total` y `payment-status-change` ya no existen. La estructura correcta es:

```xml
<!-- O19 native -->
<section class="paymentlines-container ...">
    <div class="payment-status-container d-flex ...">
        <div class="payment-status-amount d-flex ...">
            <span>statusText</span>
            <PriceFormatter price="amountText" />
        </div>
    </div>
</section>
```

XPath correcto: `//div[hasclass('payment-status-container')]`.

### Pre-existing bugs encontrados en la verificación

1. **`get_rounding_applied()`** (`payment_status.js:54`) — método O17 que ya no existe en O19 core. Se agregó wrapper en `order_model.js`.
2. **`get_foreign_rounding_applied()`** (`payment_status.js:67`, `order_model.js:288`) — método O17 que no existe en O19 (l10n_ve_pos lo tiene comentado). Se agregó stub que retorna 0.
3. **`this.props.order.*`** en `get_max_total_with_igtf()` (`order_model.js:288`) — estaba usando `this.props.order` pero el método está en el PosOrder patch, debería ser `this`. Se corrigió reemplazando por `this.compute_igtf_amount(foreignTotal) + 0`.
4. **Falta `return res`** en el for-loop de `get_total_with_tax()` — se agregó como safety.

## Docker setup

El repo de trabajo es `/home/binaural19/docker-odoov19/` (con v antes del
19), que es el que monta el contenedor Docker (`proj`). El directorio
`/home/binaural19/dockerodoo19/` (sin v) tiene código accidental de una
sesión abierta donde no era — NO sincronizar ni trabajar ahí.

## Assets regeneration

Cuando se modifica JS u OWL XML, el bundle de assets lleva un hash (ej: `d3b014b`). Si el hash no cambia después de un `-u`, verificar:
1. Que el archivo modificado esté en el directorio que el contenedor monta
2. Que el manifest tenga el asset bundle correcto (`point_of_sale._assets_pos`)
3. Que el archivo esté cubierto por el glob pattern del manifest

## IGTF Business Rules (CRITICAL — leer antes de tocar `update_igtf()`)

> **Rediseñado 2026-07-09.** La fórmula anterior documentada aquí
> (`baseNueva = baseImponible - IGTFacumulado`) tenía una DOBLE RESTA del
> IGTF acumulado que producía 341,92 Bs en vez de 348 al pagar en dos
> líneas. Fuente de verdad actual:
> `openspec/changes/l10n-ve-pos-igtf-migration/specs/frontend-igtf-calculation.md`
> y `specs/frontend-payment-creation.md`.

Resumen (ver specs para detalle y escenarios con números reales):

1. IGTF = 3% SOLO de la base de factura cubierta por líneas `apply_igtf`;
   tope 3% del total. La porción que salda deuda IGTF nunca genera IGTF.
2. Cálculo SIEMPRE en moneda principal (`line.amount`); foráneo = display,
   derivado con UNA conversión `localToForeign`. Nunca cálculo paralelo en
   foráneo ni suma de conversiones redondeadas
   (`round(a)+round(b) != round(a+b)` → bugs 341/348, 17,70/17,71, $18,23).
3. Nada de `Math.abs` ni comparaciones float crudas: `roundLocalMoney`,
   `roundForeignMoney`, `floatIsZero(v, currency.decimal_places)`. Signo por
   normalización `amt = sign * amount`.
4. Algoritmo central: `_igtfBaseState(excludeLine)` en `order_model.js`
   (rastrea base cubierta vs deuda IGTF línea a línea). Lo consumen
   `update_igtf`, `add_paymentline_without_igtf` (cierre = base restante +
   deuda + IGTF de la nueva base) y el patch de `set_foreign_amount`.
5. Al seleccionar un método `apply_igtf`, la línea se autocompleta con el
   cierre completo y la orden queda en 0 (pedido explícito de Jesús,
   2026-07; reemplaza el diseño O17 de "la deuda IGTF se paga en línea
   aparte").

### Lecciones nuevas (2026-07-09)

- **Los campos IGTF viajan por `PosOrder.serializeForORM`, NO por
  `_load_pos_data_fields`.** `deepSerialization` solo recorre campos declarados
  en ese contrato, y las líneas hijas se serializan por recursión directa,
  **saltándose** el `serializeForORM` del modelo JS hijo → un override ahí en
  `PosPayment` es código muerto; hay que inyectar los campos del pago en los
  comandos de `data.payment_ids`, emparejando por `vals.uuid`.
  **TRAMPA (costó una tarde):** declarar los campos IGTF en
  `_load_pos_data_fields` los vuelve reactivos; como `update_igtf()` los
  reescribe (hasta desde `PosOrder.setup()`), cada escritura marca `_dirty` y
  **el POS se cuelga en un bucle de render/sync, pantalla en blanco y CPU al
  100%**. Deben ser props JS planas. Ver `specs/backend-order-validation.md`.
  `export_as_JSON`/`init_from_JSON` (JS) y `_order_fields`/`_payment_fields`/
  `_export_for_ui` (Python) **no existen ni se invocan en O19** (verificado por
  grep en el core): los hooks Python ya se eliminaron del módulo.
- **`action_pos_order_paid` no tiene hook**: compara `amount_total` vs
  `amount_paid` inline y no llama a `_get_rounded_amount`/`_is_pos_order_paid`.
  `amount_total` NUNCA incluye IGTF (alimenta la factura); `amount_paid` SÍ.
  Ver `specs/backend-order-validation.md`.
- **Signo del vuelto**: el `change` del core es NEGATIVO en ventas (opuesto al
  total). Se manda como `amount_return` y el backend crea con él una línea
  `is_change` que resta de `amount_paid`. Devolverlo positivo rompe la
  validación de pago.
- **Doble suma cross-módulo**: `l10n_ve_pos/payment_status.js` sumaba
  `get_foreign_igtf_amount` sobre un `get_foreign_total_with_tax` que este
  módulo ya parchea para incluir IGTF → $18,23. l10n_ve_pos no debe saber
  de IGTF; la única fuente del total foráneo es `get_foreign_total_with_tax`.
- **numberBuffer**: llenar siempre con `formatCurrency`/`formatForeignCurrency`
  (locale-aware, 2º arg `false`), nunca `String(amount)`/`toFixed` — es_VE
  parsea `.` como separador de miles. Para métodos foráneos el buffer lleva
  el monto FORÁNEO, no el local.
- **Bypass de l10n_ve_pos en addNewPaymentLine**: para métodos `apply_igtf`
  se llama `order.addPaymentline` directo; dejar pasar el super haría que
  `set_foreign_amount(localToForeign(dueBefore))` pise el cierre con drift
  ida-vuelta y sin recargo.
- **Verificación por simulación**: los escenarios (tasa 675, factura 11.600)
  están en scripts node desechables; reproducirlos ante cualquier cambio:
  pago completo 11.948/$17,70; $10 + cierre 5.198/$7,70 (IGTF 348 exacto);
  pagar deuda 348 con Zelle no genera IGTF; sobrepago $20 da vuelto sin IGTF
  extra; reembolso espejo (-11.948, IGTF -348).
