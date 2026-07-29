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
   `update_igtf` y el patch de `set_foreign_amount` (clamp al restante).
5. **Precarga separada del IGTF (pedido explícito de Jesús, 2026-07-09,
   2ª iteración — reemplaza al "cierre en una línea" que duró unas horas):**
   toda línea nueva precarga `remainingDue` (deuda de factura + deuda IGTF
   acumulada), NUNCA el IGTF que ella misma generará; ese nace después en
   `update_igtf()` como nuevo restante, pagable con cualquier método. Pagar
   una factura completa con método `apply_igtf` son SIEMPRE dos líneas
   (parcial: tres). No hay rama especial en `addPaymentline` ni bypass en
   `addNewPaymentLine`; `add_paymentline_without_igtf` fue eliminado.

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
- **Sin bypass en addNewPaymentLine** (el bypass existió solo para el diseño
  de "cierre en una línea", ya retirado): la precarga deseada es
  `remainingDue`, exactamente lo que maneja l10n_ve_pos. El drift foráneo lo
  resuelve el clamp IGTF-aware de `set_foreign_amount`, que aplica con método
  `apply_igtf` O cuando la orden tiene deuda IGTF (sin el segundo caso, pagar
  la deuda 348 con foráneo sin apply_igtf daría 351 por reconversión).
- **El `remainingDue` del core CLAMPA a 0** en cuanto `amountPaid >= totalDue`
  y pierde el exceso. No sirve como base para componer (`core + igtf`): cuando
  una línea absorbe deuda IGTF, la composición devolvía la deuda COMPLETA
  (426,60) en vez de la pendiente (21,64). Usar la fórmula directa
  `totalDue + igtf_amount - amountPaid` (getter en order_model.js). Y las
  simulaciones deben modelar el clamp del core: una sim con `total - paid`
  sin clamp validó la versión rota.
- **`get_foreign_due`/`get_foreign_change` (l10n_ve_pos) derivan del LOCAL**
  con una conversión (`localToForeign(remainingDue/change)`): la versión que
  restaba `get_foreign_total_paid` no veía los pagos de métodos locales
  (foreign_amount = 0 vía `_recomputeForeignFromLocal`) y el restante alterno
  no bajaba al pagar en Bs. Bonus: al delegar en getters del core que este
  módulo parchea, el panel foráneo refleja el IGTF sin que l10n_ve_pos lo
  conozca.
- **Verificación por simulación**: los escenarios (tasa 675, factura 11.600)
  están en scripts node desechables; reproducirlos ante cualquier cambio:
  A) Zelle 11.600 → restante 348 → segunda línea 348 sin IGTF nuevo;
  B) Zelle $10 (6.750, IGTF 202,50) → restante 5.052,50 → Zelle → IGTF 145,50
  → restante 145,50 → tercera línea (IGTF total 348 exacto);
  pagar deuda 348 con Zelle no genera IGTF; sobrepago $20 da vuelto sin IGTF
  extra; reembolso espejo (IGTF -348); `amount_paid` final siempre
  `amount_total + igtf_amount`.

## Resuelto (2026-07-14)

### El foráneo bajo el total nativo mostraba 21,70 en vez de 21,07

Decisión tomada por Jesús: **subtítulo = conversión pura del total nativo**
(opción 1 de las tres planteadas abajo). Se eliminó por completo el override
de `get_total_with_tax()`/`get_foreign_total_with_tax()` en
`order_model.js` (este módulo ya no los redefine), dejando que
`l10n_ve_pos` sea la única fuente de verdad de esos dos getters (pura
conversión de factura, sin IGTF). El recargo IGTF solo se expone vía
`get_bi_igtf()`/`get_igtf_amount()`/`get_foreign_igtf_amount()`, consumidos
únicamente por el desglose BI IGTF/IGTF/Foreign IGTF del panel de estado de
pago (la fila TOTAL+IGTF se eliminó de la UI a pedido de Jesús).

Efecto en todos los consumidores que leían `get_foreign_total_with_tax`
(antes inconsistentes entre sí): subtítulo bajo el total nativo, panel
Restantes (`l10n_ve_pos/payment_status.js`), recibo, ticket, resumen de
venta y `serializeForORM.foreign_amount_total` (backend) — todos muestran
ahora, de forma consistente, el total de factura SIN IGTF.

Verificado antes de aplicar que esto no rompe `l10n_ve_pos_mf` (máquina
fiscal/Veri*factu): su fallback de reembolso en `PosStore.js` ya usaba
`order.totalDue` (sin IGTF) en la rama de moneda base VEF; el fix alinea la
rama de moneda foránea con ese mismo comportamiento (antes era una
inconsistencia accidental entre ambas ramas, no un diseño intencional). El
reparto proporcional del reembolso no depende de que el total cuadre con la
suma de pagos originales, así que no hay riesgo de descuadre.

Detalle completo en
`openspec/changes/l10n-ve-pos-igtf-migration/specs/frontend-igtf-calculation.md`
("Requirement: get_foreign_total_with_tax nunca incluye el IGTF").

Las tres opciones originalmente planteadas (para referencia):
- ~~Subtítulo = conversión pura del total nativo y dejar el recargo solo en
  el panel TOTAL + IGTF~~ → **elegida**.
- Ambos números IGTF-inclusive (cambiaría el total nativo mostrado).
- Un getter separado para display "total factura foráneo" vs "total
  efectivo foráneo" y que cada pantalla elija.

### foreign_amount = 0 en líneas de métodos locales

Detalle y consumidores afectados en
`l10n_ve_pos/openspec/migration-lessons.md` (Pendientes 2026-07-10). Afecta a
este módulo en `_create_payment_moves`: los apuntes foráneos del split IGTF
quedan en 0 cuando el pago fue en Bs.
