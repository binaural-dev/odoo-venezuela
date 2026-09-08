# Backend Order Validation Specification

> Añadido 2026-07-09 tras el bug *"Order %s is not fully paid."* al validar
> órdenes pagadas con métodos `apply_igtf`.

## Purpose

Definir cómo `pos.order` valida que una orden con recargo IGTF está pagada, y
qué campos deben viajar del frontend al backend para que eso funcione.

## Contrato de montos (CRÍTICO)

| Campo | Incluye IGTF | Origen |
|---|---|---|
| `amount_total` | **NO** | frontend `setOrderPrices()` = `currency.round(priceIncl)`. Alimenta la factura, que NO lleva el recargo. |
| `amount_paid` | **SÍ** | backend, `_compute_amount_paid()` = `sum(payment_ids.amount)`. Las líneas `apply_igtf` tienen `amount = base + IGTF`. |
| `igtf_amount` (order) | — | el recargo, firmado (negativo en reembolsos). |

Por tanto `amount_paid = amount_total + igtf_amount` en una orden saldada, y
`amount_difference` (= `amount_paid - amount_total`) queda en el importe del
IGTF. Es correcto y deliberado: el cliente pagó más que la factura.

### Requirement: action_pos_order_paid compara contra el total CON IGTF

El core (`point_of_sale/models/pos_order.py::action_pos_order_paid`) exige
`float_is_zero(amount_total - amount_paid)` con lógica **inline**: no llama a
`_get_rounded_amount` ni a `_is_pos_order_paid`, así que **no hay hook
factorizado**. El único punto de extensión es sobreescribir el método.

`l10n_ve_pos_igtf/models/pos_order.py`:

- Si `currency_id.is_zero(igtf_amount)` → `super()` (órdenes normales intactas).
- Si hay IGTF → réplica del core comparando contra
  `_get_total_with_igtf()` = `currency.round(amount_total + igtf_amount)`.
- **REVISAR EN CADA UPGRADE**: es una copia deliberada.

`_is_pos_order_paid` se sobreescribe igual, para el asistente de pago desde
backend (`point_of_sale/wizard/pos_payment.py`).

#### Scenarios (factura 11.600 Bs, IGTF 348)

| Caso | amount_total | igtf_amount | amount_paid | Resultado |
|---|---|---|---|---|
| Venta sin IGTF, exacto | 11.600 | 0 | 11.600 | valida (vía `super()`) |
| Venta IGTF, exacto | 11.600 | 348 | 11.948 | valida |
| Venta IGTF, sobrepago | 11.600 | 348 | 11.948 (tras línea de vuelto) | valida |
| Venta IGTF, sin pagar el recargo | 11.600 | 348 | 11.600 | **error** (correcto) |
| Reembolso IGTF | −11.600 | −348 | −11.948 | valida |

### Requirement: convención de signo del vuelto

`PosOrderAccounting.change` (core) devuelve el vuelto con el **signo opuesto al
total**: negativo en ventas, positivo en reembolsos. `setOrderPrices()` lo manda
como `amount_return`, y `_process_payment_lines` crea con él una línea de pago
`is_change=True` que se **suma** a `payment_ids` (y por tanto resta de
`amount_paid`). Después `_compute_prices()` recalcula
`amount_return = -sum(pagos negativos)`.

Nuestro override de `change` debe respetar ese signo. Devolverlo en positivo en
una venta inflaría `amount_paid` y dispararía el mismo `UserError`.

Al desarrollar el `isNegative ? -round(total) : round(total)` del core, ambas
ramas colapsan en `round(priceIncl + igtf_amount - amountPaid + rounding)`, así
que no hacen falta `Math.abs` ni ramas por signo.

### Requirement: remainingDue normalizado por signo

El guard "la deuda IGTF ya está cubierta" debe compararse en espacio normalizado
(`sign * base <= 0`), no `base <= 0`: en reembolsos `base` es negativo desde el
primer momento y la versión sin normalizar devolvía 0 (orden aparentemente
saldada antes de pagar nada).

## Requirement: los campos IGTF viajan por `PosOrder.serializeForORM`

Cómo funciona la serialización en O19 (`related_models/serialization.js`):

- `deepSerialization` recorre **solo los campos declarados en
  `_load_pos_data_fields`**, y al terminar hace `record._dirty = false`.
- Las líneas hijas (`payment_ids`, `lines`) se serializan por **recursión
  directa** a `deepSerialization`, saltándose el `serializeForORM` del modelo JS
  hijo. Un override de `PosPayment.serializeForORM` es, por tanto, **código
  muerto**: nunca se invoca para pagos anidados en la orden.
- `export_as_JSON` / `init_from_JSON` / `_order_fields` / `_payment_fields` /
  `_export_for_ui` **no existen ni se invocan** en O19 (verificado por grep en
  el core). Todo eso es herencia muerta de O17.

### TRAMPA: no declarar los campos IGTF en `_load_pos_data_fields`

Declararlos ahí los convierte en **campos reactivos** del modelo JS. Como
`update_igtf()` los reescribe en cada recálculo —incluso desde
`PosOrder.setup()`, que corre durante el arranque del POS— cada escritura marca
el registro `_dirty` y dispara el ciclo de render/sincronización. Resultado
observado (2026-07-09): **el POS se queda en blanco con el navegador al 100% de
CPU en un bucle**. `load_data` responde 200; el bucle es puramente cliente.

Los campos IGTF deben quedarse como **props JS planas** (no reactivas) e
inyectarse en el único momento en que se sincroniza, dentro de
`PosOrder.serializeForORM` (`order_model.js`):

- Nivel orden: `data.igtf_amount`, `data.bi_igtf`.
- Nivel pago: recorrer los comandos de `data.payment_ids`
  (`[0, 0, vals]` / `[1, id, vals]`) y emparejar por `vals.uuid` con la línea de
  pago del cliente, escribiendo `include_igtf`, `igtf_amount` y
  `foreign_igtf_amount`. `uuid` sí está en el contrato de `pos.payment`, y el
  `stack` de `deepSerialization` ya está resuelto cuando `super()` retorna.

Sin esa inyección, los campos de `pos.payment` nunca llegan al backend y
`_create_payment_moves` no separa el recargo hacia `customer_account_igtf_id`,
en silencio.

Contraste: `l10n_ve_pos` **sí** declara `foreign_amount`/`foreign_rate` en
`_load_pos_data_fields` (son reactivos) porque solo se escriben desde
`setAmount`/`set_foreign_amount`, es decir en respuesta a acciones del usuario,
nunca desde `setup()` ni durante un render.
