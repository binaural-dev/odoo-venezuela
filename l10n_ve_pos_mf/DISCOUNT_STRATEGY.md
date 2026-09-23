# Global Discount vs Line Discount in Fiscal Printing (TFHKA)

## Context

This note compares how discounts are calculated in POS vs how TFHKA applies fiscal commands, based on real tests in this project.

Current config observed during tests:

- Tax model: price + tax (tax is not included in product price)
- Main VAT rate: 16%
- Fiscal printer integration: Web Serial (`l10n_ve_pos_mf`)

> **STATUS (see "Evolución: Strategy C" at the end of this document).**
> Strategy A, described immediately below, is the historical decision, its
> arithmetic is still the basis of everything, and it remains **the default
> behavior**. For the **sales invoice** (`printInvoice`) it can optionally be
> superseded by **Strategy C**, which prints each line's own **campaign**
> discount using the `q-` command (discount by AMOUNT) instead of silently
> sending a net price, while the **global** POS discount keeps being shown as a
> single aggregate at the foot — see "Strategy C corregida: campaña por línea,
> global agregado al pie". Strategy C is gated behind the `pos.config`
> switch `mf_line_discount_via_q_command`, **default OFF**: with the switch off
> the printed invoice is byte-for-byte Strategy A. NC/ND always behave exactly
> as described under Strategy A. **Strategy C has NOT been validated against a
> physical TFHKA printer** — read the "Riesgo abierto" section before enabling
> the switch for a customer.

## Decision (implemented)

**Strategy A: line-discount cascade applied uniformly.**

The global POS discount is mathematically redistributed onto the base price of each positive line BEFORE the request reaches the fiscal driver. Result: the printer receives only positive items with pre-discounted net unit prices. The arithmetic becomes identical to having the cashier apply the same percent on every line individually.

### Why this resolves the mismatch

| Path | Math | Result |
|---|---|---|
| Line discount on a 100 Bs item (tasa 1) | 100 × (1 − 10%) = 90 base → IVA 14,40 | **104,40** |
| Global POS discount of 10% in Odoo: line 100, "discount product −10" | Odoo computes: 116 − 10 = 106 (subtotal − amount, no tax on discount) | **106,00** (different) |
| Global POS discount using **Strategy A** | 100 × (1 − 10%) = 90 base → IVA 14,40 | **104,40** (matches line-discount) |

The mismatch previously occurred because:
- Line-discount applied to base — tax is recomputed.
- Global discount applied after tax — `q-` subtracts from the post-tax subtotal.

Strategy A forces the global discount into the same regime as line-discount: applied to base. Totals then match.

## Implementation summary

### PosStore.js (`_applyDiscount` + `_convertOrderForDriver`)

```javascript
_applyDiscount(unitPrice, percent) {
    const value = Number(unitPrice || 0) * (1 - Number(percent || 0) / 100);
    return round_pr(value, this.currency?.rounding || 0.01);
}
```

Cascade:

1. Detect negative lines (`price_unit < 0`) → sum them into `globalDiscountAmount` (raw POS amount).
2. Compute `positiveBaseSum = Σ ((1 − lineDiscount/100) × price_unit × quantity)` for positive lines.
3. Compute `globalRate = (globalDiscountAmount / positiveBaseSum) × 100`, clamp at 100.
4. Apply `finalUnitPrice = (1 − lineDiscount/100) × (1 − globalRate/100) × price_unit` per positive line.
5. If `globalRate` clamped to 100%, set `global_clamped = true` to surface an advisory pop-up.

### TfhkaDriver.js (`_appendDiscountInfoLine`)

A new helper emits ONE informational line on the printed ticket:

```
iXX DESC. GLOBAL 15% = 15.00
```

If `global_clamped === true`, a second line is emitted:

```
iXX DESC. GLOBAL EXCEDIO SUBTOTAL
```

These lines are sent in the **factura** footer only and never appear in NC/ND.

### Clamping policy

If the global POS discount exceeds the value of the underlying base, the rate is clamped to 100% and the user sees a pop-up:

> "El descuento global (X.XX Bs) excede el subtotal de las líneas. Se aplicó el máximo permitido (100.00%) en el comprobante."

Receipt is still printed.

### NC / ND

Strategy A is **not** propagated to Notas de Crédito / Débito. NC/ND retain the legacy `q-` behavior because they are refund/charge documents that don't carry a "global POS discount" context in the same way. Information line and clamp warning are only emitted in Factura.

## What this affects

- **Math**: Total printed by the fiscal printer matches what Odoo computes for an equivalent line-discount situation. Eliminates the "tax discrepancy" complaint.
- **Ticket readability**: The single line `DESC. GLOBAL 15% = 15.00` preserves audit visibility.
- **Overwrite policy**: A newly assigned global discount always overwrites the discount on every positive line (reset to 0% then set to the flat global rate). It does **not** compose with any pre-existing per-line discount or with a previously applied global discount. This avoids uneven rates between lines added before vs. after a global discount is set (previously caused "split"/unequal discounts when a new line was added and the global discount was reassigned).
- **No new fiscal commands introduced** — still uses only `!`, `iXX`, `3`, `1XX`, `2XX`, `101`, `199`. No `p-` per-line or negative-priced items. Compatible with the existing printer firmware.
- **No firmware-specific assumptions** beyond what was already working.

## What was tried before (and discarded)

### Option "negative line as item" (single experiment)

Tried sending the discount as a negative-priced item command (no `q-`). Result on the real printer:

- Command like `<STX> -000000100000001000|DISC|Descuento<ETX>` was rejected with NAK.
- Transaction stuck in `STS1=0x61`; recovery with `9` / `199` did not stabilize.

The firmware rejects negative-priced items in this invoice flow. Rolled back.

### Reference: legacy IoT (`binaural_iot_mf`)

The legacy IoT reference implementation (`SerialFiscalDriver.py`) follows the same `q-` approach. There is no historical "send discount to fiscal" pattern in production that would have solved this arithmetic.

## Limitations & open questions

- **10-line info buffer**: TFHKA limits informational `iXX` lines to ~10 per document. Each header line (address/phone) and footer line consumes one slot. With Strategy A, we get 1 (info) + 1 (clamp warning if needed) + headers + footers. For a document with > 7 header lines + 8 footer lines, the discount info line may be skipped (logged warning in browser console).
- **Clamp >100%**: Treated as a soft cap with pop-up rather than a hard rejection. Discuss with business if they prefer strict rejection.
- **Coexistence with line discount**: The global discount always overwrites `line.discount` on every positive line (no composition). Assigning a global discount is a flat, idempotent operation: every time it is (re)applied, all lines are reset to 0% first, then set to the same rate.

## Tests

Includes in `tfhka_driver_tests.js`:

- `_applyDiscount` helper unit test (`round`, percent cases, cascade).
- Strategy A integration: no `q-`, discount info line emitted, metadata returned to caller.
- Clamp integration: second "EXCEDIO SUBTOTAL" line present, `global_clamped=true`.
- Pre-existing "Impresión de factura con impuestos y métodos de pago" coverage still pass for the discount/output sequence.

## Operational checklist after upgrade

1. `docker exec "odoo-odoo17" odoo -d "bd17" --workers=0 --http-port=8079 -u "l10n_ve_pos_mf" --stop-after-init`
2. Hard refresh POS (`Cmd+Shift+R`).
3. Repeat the discount comparison test. Confirm:
   - Total in Odoo equals Total in printed receipt.
   - The line `DESC. GLOBAL X% = Y.YY` appears on the receipt.
4. If the discount exceeds the subtotal, the pop-up "excede el subtotal" appears.

---

# Evolución: Strategy C — descuento visible por línea vía `q-`

> **Historia del nombre.** Una primera propuesta ("Strategy B") usaba el comando
> `p-` (descuento por **porcentaje**). La revisión formal la rechazó por tres
> problemas Critical, todos con el mismo modo de falla — un descuadre en el
> cierre `199` puede trabar la impresora física. **Strategy C reemplaza `p-`
> por `q-` (descuento por MONTO)**, que tiene la misma semántica posicional
> (aplica al ítem inmediatamente anterior) pero elimina los tres problemas de
> raíz. Este documento describe Strategy C; `p-` ya no se usa en ninguna parte
> del código.

> **Alcance: SOLO la factura de venta (`printInvoice`), y SOLO con el
> interruptor `mf_line_discount_via_q_command` en ON.**
> `printCreditNote` y `printDebitNote` NO fueron tocados: siguen enviando el
> precio neto (`price_unit`), siguen usando `q-` para el descuento global
> **agregado al subtotal** y siguen imprimiendo la línea "DESC. GLOBAL = X" en
> el pie.

## Por qué se revisó la decisión

Strategy A se adoptó bajo el supuesto de que el protocolo no permitía llevar el
descuento a la impresora. Ese supuesto se apoyaba en **un solo experimento**: el
de enviar el descuento como **ítem con precio negativo**, que la impresora real
rechazó con NAK (ver "What was tried before" arriba). Esa conclusión sigue
siendo válida *para ese mecanismo*.

Al releer el manual del fabricante se confirmó que existe un mecanismo
**distinto**: los comandos `q-` / `q+` (descuento / recargo por **monto**) y
`p-` / `p+` (por porcentaje). No son ítems negativos: se envían
**inmediatamente después de un ítem positivo ya registrado** y modifican **sólo
ese ítem**.

En realidad `q-` **ya está en producción en este proyecto**: es exactamente el
comando que `printCreditNote` / `printDebitNote` usan hoy para el descuento
global, con el mismo formato de dígitos. La única diferencia de Strategy C es
**dónde** se coloca: tras cada ítem en vez de tras el subtotal.

### Evidencia en el manual

`[VE]Manual_de_Protocolos_y_Comandos_Venezuela_V0805R00`, V8.5.0:

- **Tabla 22, págs. 27-28 — "DESCUENTO Y RECARGO POR MONTO"**: documenta
  explícitamente el formato del argumento de `q-` / `q+`, cuyos dígitos
  **dependen del Flag 21**. Es la cita correcta para el formato; la versión
  anterior de este documento citaba la Tabla 19 (pág. 24), que corresponde al
  comando `PT` (programación de tasas de impuesto) y **no aplica aquí**.
  En el código esos dígitos son `FLAG21_CONFIGS[flag].disc_int` /
  `.disc_decimal` — los mismos que ya consumía el `q-` de NC/ND.
- **Tabla 29, pág. 34** (factura) y **Tabla 31, pág. 37** (nota de crédito):
  tras un ítem, el comando de descuento se imprime como un renglón `DESC` bajo
  **ese** producto, no al pie del documento.
- **Desglose por tasa de impuesto, pág. 35** — la evidencia más fuerte de la
  atribución por ítem. El pie del mismo ejemplo desglosa los buckets
  EXENTO / BI G16% / BI R8% / BI A31% / PERCIBIDO, y **sólo cuadran si cada
  descuento y cada recargo se imputa al ítem inmediatamente anterior, bajo la
  tasa de ese ítem**. Si el descuento se aplicara al subtotal, los buckets
  individuales no darían. Esto es más concluyente que la simple suma del
  `SUBTTL`, que podría cuadrar por coincidencia.
- **Aritmética del `SUBTTL` del ejemplo (corregida).** La Tabla 29 registra
  **7 ítems**, no 5: además de los cinco que contribuyen — 10 (con `−10%` → 9),
  20 (con `+10%` de recargo → 22), 30 (con `−10,00` por monto → 20),
  40 (con `+10,00` → 50) y 50 percibido — el ejemplo incluye **dos ítems que
  el propio ejemplo revierte**: uno cancelado con el **comando de corrección
  `k`** (que anula el ítem anterior; `k` no es un prefijo de registro de ítem)
  y otro **anulado con el prefijo `£`**. Ambos **aportan 0,00 al total**. Con
  los 7 contabilizados,
  `9 + 22 + 20 + 50 + 50 + 0 + 0 = 151,00`, que es el `SUBTTL` impreso
  (Bs 151,00). La versión anterior de este documento omitía los dos ítems
  anulados, de modo que la suma "cuadraba" sin ser reproducible contra el
  ejemplo completo.
- El checklist de certificación del propio manual (pág. 86-88) distingue
  explícitamente la prueba **"Factura con descuento sobre un ítem"** (nº 9) de
  **"Factura con descuento sobre el subtotal"** (nº 12), lo que corrobora que
  existen los dos mecanismos y que son distintos.

## Formato del argumento de `q-`

**Depende del Flag 21** (Tabla 22, págs. 27-28):

| Flag 21 | `disc_int` | `disc_decimal` | Ejemplo: 15,00 Bs |
|---|---|---|---|
| `00`, `01`, `02` | 7 | 2 | `q-000001500` |
| `30` | 15 | 2 | `q-00000000000001500` |

En el código se emite con
`this._formatAmount(discountAmount, config.disc_int, config.disc_decimal)`,
donde `config` es el MISMO objeto `FLAG21_CONFIGS[...]` que `printInvoice` ya
resolvía para el precio y la cantidad del ítem — y la misma llamada que ya hace
`printCreditNote` para su descuento global.

### Guarda de desbordamiento (no hay límite de 100%)

Con un monto no existe el límite de 99,99% que imponía el campo de porcentaje
de `p-`. El único límite es cuántos dígitos enteros reserva el Flag 21
(9.999.999,99 Bs con `disc_int = 7`).

**Cómo se comprueba.** No basta con `monto < 10 ** disc_int`: `_formatAmount`
hace `toFixed(decPart)` ANTES de partir el número, y ese redondeo puede subir un
dígito entero justo en el borde. Caso reproducido:

```
9999999.996 < 1e7                  -> true          (la comparación deja pasar)
_formatAmount(9999999.996, 7, 2)   -> "1000000000"  (10 caracteres, no 9)
```

Por eso la guarda es `_amountFitsField(valor, intDigits, decDigits)`, que
**formatea primero y mide la cadena**: `formateado.length === intDigits +
decDigits`. Es la única forma fiable, y se aplica a los DOS campos del camino
`q-`.

**Dos guardas, dos degradaciones distintas:**

| Qué desborda | Qué se degrada | Cómo se reporta |
|---|---|---|
| el **monto del descuento** (`disc_int`) | **no se emite el `q-`**; el ítem queda impreso a su precio **bruto** | `line_discount_overflow_lines` |
| el **precio bruto del ítem** (`max_amount_int`) | **TODO EL DOCUMENTO** vuelve al comportamiento histórico (ver "C2" abajo) | `line_gross_price_overflow_lines` + `line_discount_via_q_document_degraded` |

La primera guarda (monto de descuento) sigue degradando **una sola línea**:
omite el `q-` de esa línea puntual y la deja impresa a su precio bruto, sin
afectar al resto del documento.

> **C2 (revisión formal, corregido):** la guarda del **precio bruto** ya NO
> degrada una sola línea — degrada el **documento completo**. Antes, si el
> bruto de una línea no cabía, sólo esa línea volvía a precio neto sin `q-`,
> mientras el resto seguía por el camino `q-`. El problema: el `q-` **agregado**
> tras el subtotal (`global_only_discount_amount`/`_rate`) ya lo había
> calculado `PosStore` ANTES de que el driver decidiera degradar nada, así que
> seguía incluyendo la porción global de la línea degradada — que ya había
> quedado embebida silenciosamente en su precio neto. Resultado: esa porción se
> restaba **dos veces** (una en el precio neto de la línea, otra en el `q-`
> agregado del pie), duplicando el descuento para esa línea.
>
> El fix: una **pre-pasada** sobre `orderData.lines`, ANTES de construir
> `phase1Commands`, comprueba con `_amountFitsField` si el precio BRUTO de
> **cada** línea cabría. Si **alguna** no cabe, se fuerza `lineDiscountViaQ =
> false` para **todo el resto del método** — como si
> `orderData.line_discount_via_q` hubiera venido en `false` desde el origen.
> El documento completo cae, byte por byte, al comportamiento histórico ya
> validado (Estrategia A: todos los ítems a precio neto, sin `q-` por línea; el
> pie usa `global_discount_amount`/`_rate` **históricos**, no los `_only`,
> porque la copia de `orderData` con los campos "solo global" para el pie sólo
> se arma `if (lineDiscountViaQ)`).
>
> La guarda **por línea** original (la que degradaba una sola línea) se dejó en
> el código, pero con la pre-pasada es **inalcanzable en la práctica**: si
> cualquier línea desbordaba, `lineDiscountViaQ` ya quedó forzado a `false`
> para todo el documento, así que ninguna línea vuelve a intentar el camino
> bruto. Se conserva como red de seguridad silenciosa (documentado en el
> código, no es descuido) por si algún día el loop de impresión iterara una
> colección distinta de la de la pre-pasada.
>
> `fiscalResponse.line_discount_via_q_document_degraded` es un booleano nuevo
> que distingue "degradó todo el documento" (siempre `true` cuando
> `line_gross_price_overflow_lines` no está vacío, con el fix) de una
> degradación parcial (que con el fix ya no puede ocurrir). El `PosStore` lo
> usa para dar un mensaje de pop-up más preciso.

Ambas guardas sólo actúan en el camino nuevo (interruptor en ON). Con el
interruptor en OFF no se agrega ninguna comprobación: el comportamiento es
byte por byte el histórico.

Nunca se construye una trama malformada, que es el escenario que podría trabar
la impresora en el cierre `199`.

## Qué resuelve respecto de la propuesta con `p-`

| Problema de la revisión | Cómo lo resuelve `q-` |
|---|---|
| **C1 — sin interruptor de apagado** | Campo `mf_line_discount_via_q_command` en `pos.config`, **default OFF**. Con el flag apagado el comportamiento es byte por byte el de Strategy A. |
| **C2 — una línea al 100% no cabe en el campo** | No aplica: el 100% se expresa como el monto total de la línea. No hay techo porcentual. |
| **C3 — la impresora tendría que rehacer la aritmética del %** | No aplica: el monto **exacto** lo calcula Odoo (`round((bruto − neto) × cantidad)`) y la impresora sólo lo resta. No hay redondeo propio del equipo, no hay ambigüedad con cantidad > 1, no hay pérdida de precisión con descuentos de decimales "feos". |

## El interruptor `mf_line_discount_via_q_command`

- Modelo: `pos.config`, booleano, `default=False`.
- Espejo en `res.config.settings`: `pos_mf_line_discount_via_q_command`.
- Vista: sección "Fiscal Machine (Web Serial API)" de los ajustes del POS
  (`l10n_ve_pos_mf/views/res_config_settings.xml`, dentro del record
  `view_res_config_settings_pos_mf`).
- Llega al driver como `line_discount_via_q` dentro del payload que arma
  `_convertOrderForDriver`.

**Con el flag en OFF (default)** `printInvoice` ignora `gross_price_unit` y
`discount_amount`, registra el ítem con `price_unit` (neto) y vuelve a emitir la
línea agregada "DESC. GLOBAL = X" del pie: exactamente la Strategy A descrita al
inicio de este documento. Activación gradual: encender el flag cliente por
cliente, sólo después de validar el comando contra su impresora real.

## Strategy C corregida: campaña por línea, global agregado al pie

> Esta sección **corrige** el diseño original de Strategy C tras probarlo
> contra impresora física. Lo describe el ANTES y el AHORA porque el cambio es
> conceptual, no cosmético.

### El problema

Un pedido puede llevar **dos descuentos de naturaleza distinta a la vez**:

| | De dónde sale | Sobre qué se calcula |
|---|---|---|
| **Campaña** | regla de lista de precios por categoría / temporada / antigüedad (módulo `binaural_pos_pricelist_line_discount`) | **cada producto individual** |
| **Global** | botón "Descuento Global" del POS | **el TOTAL de todo el pedido** |

La primera versión de Strategy C los **fusionaba en un solo porcentaje por
línea** (`composeDiscountPercent(campaña, global)`) y emitía un único `q-` con
el monto ya combinado, además de **suprimir** la línea agregada del pie. En el
ticket real esto es incorrecto: el cliente ve un "DESC" bajo cada producto por
un monto que no corresponde a la promoción de ese producto, y no queda rastro
de que hubo un descuento sobre el total del pedido.

### El comportamiento corregido

| | ANTES (Strategy C v1) | AHORA (Strategy C corregida) |
|---|---|---|
| `q-` pegado al ítem | monto **compuesto** (campaña + global) | monto de **SOLO su descuento de campaña** |
| Descuento global | disuelto dentro de los `q-` por línea | **`q-` agregado tras el subtotal `3`** |
| Línea de MONTO al pie (`DESC. GLOBAL = X`) | **suprimida** | **se emite**, con la porción **no atribuible a campaña** |
| Línea de AVISO (`DESC. GLOBAL EXCEDIO SUBTOTAL`) | se emitía | se emite igual |

Es decir: los `q-` por línea y la línea agregada del pie **coexisten**, cada uno
representando lo suyo. El pie vuelve a verse como en la Strategy A, pero ahora
acompañado de los `DESC` por producto.

### Por qué el global también necesita un `q-` agregado (y no sólo la línea `iXX`)

La línea `iXX DESC. GLOBAL = X` es **informativa**: no mueve ni un céntimo del
cálculo interno de la impresora. En Strategy A eso no importaba porque el
descuento global ya venía **embebido en el precio neto** de cada ítem.

Con la separación, los ítems se registran a precio **bruto** y sus `q-` sólo
descuentan la campaña — de modo que el subtotal que la impresora tiene en mano
es el **neto de campaña**, todavía sin el global. Los montos de pago `2XX`, en
cambio, los calcula Odoo y vienen netos de **ambos** descuentos. Si el global no
se aplicara como comando fiscal, el cierre `199` encontraría pagos por debajo de
su propio total y **lo rechazaría con NAK**.

Por eso `printInvoice` emite, justo después del subtotal `3`:

```
q-<porción global>
```

Es **exactamente el mismo comando, en la misma posición**, que
`printCreditNote` / `printDebitNote` ya usan en producción para su descuento
global. No es un mecanismo nuevo: es el camino ya probado, reutilizado en la
factura.

### Cómo se calcula la porción global

> **C3 (revisión formal, ticket físico 2026-09-23 — corregido, y verificado
> numéricamente con las funciones reales de `DiscountMath`).** La versión
> original de esta sección derivaba `globalOnly` **siempre por diferencia** de
> dos sumas por línea ya redondeadas:
>
> ```
> descuentoCampañaLínea = round(bruto × qty) − round(netoSoloCampaña × qty)
> descuentoTotalLínea   = round(bruto × qty) − round(netoFinal × qty)
>
> globalOnly = max(0, Σ descuentoTotalLínea − Σ descuentoCampañaLínea)
> ```
>
> Un ticket real (2026-09-23) mostró un desfase de **1 céntimo**: Total Odoo
> 6.757,43 / BI 5.825,37 imprimió Total 6.757,44 / BI 5.825,38 / "DESC 1.028,00"
> (el real, en Odoo, era −1.028,01). La causa **no** estaba en la resta de sumas
> en sí, sino en cómo se calculaba `descuentoTotalLínea` en el camino **ON**
> (`native_global_discount_line` en `true`, sin `preAppliedMeta`): ahí
> `netoFinal` se obtenía aplicando `globalRate` —una tasa YA redondeada a 2
> decimales— en cascada sobre cada línea, en vez de usar el monto EXACTO
> `globalDiscountAmount` que la propia función ya tenía calculado (la suma
> directa de los montos de las líneas NEGATIVAS, la línea nativa "Descuento" de
> Odoo). Esa cascada por línea introducía el redondeo que causaba el desfase.
>
> **Fórmula corregida** — distinta por camino, porque el significado de
> `globalDiscountAmount` (ya calculado arriba en la función) es distinto en
> cada uno:
>
> ```
> globalOnlyDiscountAmount = preAppliedMeta
>     ? max(0, round(globalDiscountAmount − Σ lineCampaignDiscountAmount))
>     : globalDiscountAmount;
>
> globalOnlyRate = globalRate;   // la misma variable, exacta en AMBOS caminos
> ```
>
> - **Camino ON** (`preAppliedMeta` es `null`): `globalDiscountAmount` YA es
>   "sólo global" (la campaña vive enteramente en el % propio de cada línea de
>   producto, nunca mezclada en la línea negativa) — se usa DIRECTO, sin restar
>   nada.
> - **Camino OFF** (`preAppliedMeta` presente): `preAppliedMeta.global_discount_amount`
>   es el descuento TOTAL COMBINADO (campaña + global, porque
>   `_applyGlobalDiscountBeforeValidation` compuso ambos con
>   `composeDiscountPercent` y sumó el descuento real ya con el % final). AQUÍ
>   sí hace falta restarle `Σ lineCampaignDiscountAmount` (el mismo acumulado
>   que ya se calcula por línea para el fix de C1) para aislar la porción
>   global — es una diferencia de sumas, pero SEGURA en este camino, porque las
>   dos provienen del `line.discount` REAL que Odoo aplicó, no de una tasa
>   re-derivada.
>
> ⚠ **Variante evaluada y descartada.** Se consideró usar, para el camino OFF,
> el monto CRUDO de la línea de descuento nativa ANTES de componerse con
> campaña (`inference.pendingDiscountAmount`, expuesto como un campo nuevo
> `global_only_discount_amount` en `_mf_global_discount_meta`). Parecía más
> "directo" al no pasar por ninguna resta de sumas redondeadas, pero se
> verificó numéricamente contra el caso de referencia de abajo (3 líneas de
> 34.266,88, 90% campaña, compuesto al 91,5%) que da **1.542,01**, mientras que
> lo que Odoo realmente cobra (aplicando el % COMPUESTO ya redondeado por
> `composeDiscountPercent`, que es lo que de verdad determina el subtotal de
> cada línea) es **1.542,03** — un desfase de 2 céntimos, en la dirección
> contraria, que habría arriesgado un NAK en el cierre `199`. Se descartó esa
> variante; el campo `global_only_discount_amount` NO se agregó a
> `_mf_global_discount_meta`, y `_applyGlobalDiscountBeforeValidation` queda
> sin cambios de C3 (el fix vive enteramente en `_convertOrderForDriver`).

`netoSoloCampaña` se obtiene aplicando `campaign_discount_percent` (el **%
puro** de la regla) sobre el precio bruto. Ese dato **no** se puede derivar de
`line.discount`: con `native_global_discount_line` en OFF ese campo ya fue
reescrito con el porcentaje compuesto. Por eso `get_data_invoice` propaga
`campaignDiscountPercent` —y no `campaignDiscountAppliedPercent`, que es el ya
compuesto— hasta `invoice_lines`.

La identidad que hace cuadrar el ticket se sigue cumpliendo, ahora sin el
desfase de redondeo:

```
Σ(q- por línea) + q- agregado == descuento total real que cobra Odoo
```

### Campos nuevos (y por qué no se pisaron los viejos)

`_convertOrderForDriver` agrega **dos campos nuevos** a nivel de orden:

- `global_only_discount_amount` — la porción calculada arriba.
- `global_only_discount_rate` — su tasa contra el neto de campaña, para que la
  condición `rate > 0 && amount > 0` de `_appendDiscountInfoLine` se encienda y
  se apague junto con el monto.

`global_discount_amount` / `global_discount_rate` / `global_clamped`
**conservan su semántica histórica, sin tocar**. No es cosmético: ese mismo
campo `global_discount_amount` es el que `printCreditNote` / `printDebitNote`
convierten en su `q-` **fiscal** agregado. Reescribirlo habría cambiado el total
impreso de toda nota de crédito o débito. Los históricos siguen alimentando
además el pop-up de clamp y el camino con el interruptor en OFF.

Sólo `printInvoice`, y sólo con `line_discount_via_q` en ON, usa los campos
nuevos.

### Limitación conocida: descuento MANUAL por línea

Si el cajero teclea un porcentaje directamente sobre una línea (numpad
"Descuento"), esa línea **no tiene marca de campaña**: llega con
`campaign_discount_percent = 0`. En consecuencia **no lleva `q-` propio** y su
descuento completo se contabiliza dentro del agregado "DESC. GLOBAL" del pie.

El ticket sigue cuadrando al céntimo (la identidad de arriba se cumple igual),
pero la atribución visual es imprecisa: un descuento que el cajero aplicó a un
producto concreto aparece como si fuera del total del pedido. **No se corrige
en esta iteración**; queda documentado. Resolverlo requeriría una marca
equivalente a `campaignDiscountPercent` para el descuento manual, que hoy no
existe.

> **C1 (revisión formal): marca de campaña desfasada por un descuento MANUAL
> posterior *distinto* sobre una línea que YA traía campaña.** Caso distinto
> del de arriba (que es sobre una línea SIN marca): aquí la línea SÍ tiene
> `campaignDiscountPercent`/`campaignDiscountAppliedPercent`, pero
> `orderline_model.js` sólo limpia esa marca cuando el descuento vigente
> coincide EXACTO con el último que ella misma escribió. Si el cajero teclea a
> mano un % distinto (mayor o menor) sobre esa línea, la marca queda
> desfasada: sigue apuntando al % de campaña original aunque `line.discount` ya
> no lo refleje. Sin corrección, `campaign_discount_percent` podía llegarle a
> `_convertOrderForDriver` MAYOR que el descuento real que Odoo cobra en esa
> línea, y el `q-` de campaña salía impreso por un monto mayor al real.
>
> **Fix aplicado (defensivo, no depende de arreglar el desfase de la marca):**
> en `_convertOrderForDriver`, `lineCampaignDiscountAmount` se acota con
> `Math.min(lineCampaignDiscountAmountRaw, lineTotalDiscountAmount)` —
> `lineTotalDiscountAmount` (el descuento TOTAL real de la línea, campaña +
> global) se calcula de todos modos en la misma función; el fix sólo lo mueve
> antes en el `.map()` para tenerlo disponible como tope. Garantiza el
> invariante "nunca se imprime por campaña más de lo que la línea descuenta en
> total", pase lo que pase con la marca.
>
> **No se tocó** `orderline_model.js` (limpiar la marca también cuando el
> manual difiere, no sólo cuando coincide): el core de `point_of_sale` que
> define `set_discount()` no está disponible en este checkout para verificar
> con qué otros flujos internos podría interferir un patch ahí (p. ej. el
> propio `_applyGlobalDiscountBeforeValidation` ya llama
> `line.set_discount(combinedPct)` tras actualizar
> `campaignDiscountAppliedPercent`, así que un patch mal calibrado podría
> introducir una regresión sutil en ese flujo). El `Math.min` en
> `_convertOrderForDriver` ya cierra el riesgo fiscal (lo único que puede
> imprimirse) sin necesidad de tocar ese archivo.

### Otros dos cambios de comportamiento que conviene tener presentes

1. **El aviso de clamp nunca se suprime**, y ahora además sobrevive al caso en
   que la porción global agregada queda en 0 (pedido cuyas líneas ya estaban
   todas al 100% de campaña). Es el **único rastro impreso** de que el descuento
   excedió el subtotal: el pop-up del POS sólo lo ve el cajero, en pantalla y en
   el momento.

2. **Una línea regalada SÍ aparece en el ticket.** Con el flag en OFF su precio
   neto es 0,00 y el ítem nunca llega a la impresora (`if (linePrice <= 0)
   continue`, comportamiento histórico). Con el flag en ON se envía a precio
   bruto y su `q-` descuenta el total, así que el producto queda **visible en el
   comprobante con su descuento del 100%**. Conviene avisarlo al activar el flag
   en un cliente que ya trabaja con promociones de 2x1 o regalos.

## Qué cambia en el ticket (con el flag en ON)

| | Strategy A (flag OFF) | Strategy C corregida (flag ON, sólo factura) |
|---|---|---|
| Precio enviado del ítem | neto, ya descontado | **bruto**, sin descontar |
| Descuento de campaña | invisible por línea | **`DESC` con su monto bajo cada producto**, con su propia tasa de impuesto |
| Descuento global | embebido en el precio neto de cada ítem | **`q-` agregado tras el subtotal `3`** |
| Línea de MONTO al pie (`DESC. GLOBAL = X`) | se emite (monto histórico) | **se emite** (porción no atribuible a campaña) |
| Línea de AVISO al pie (`DESC. GLOBAL EXCEDIO SUBTOTAL`) | se emite si hubo clamp | se emite si hubo clamp |
| Línea con **100% de descuento** | **se omite del ticket por completo** (el neto es 0 y `if (linePrice <= 0) continue`) | **se imprime**: precio bruto + su `q-` por el total de la línea |
| Comandos extra | ninguno | `q-<campaña>` tras cada ítem con campaña, y `q-<global>` tras el subtotal |

### Caso numérico de referencia (pedido real de campo)

Tres líneas del mismo producto a **34.266,88** con **90% de campaña**, más un
botón de Descuento Global que en Odoo genera una línea "Descuento" de
**−1.542,01** (≈15% del neto de campaña). Compuesto por línea:
`100 − (10 × 85)/100 = 91,5%`.

| | por línea | × 3 |
|---|---|---|
| Bruto | 34.266,88 | 102.800,64 |
| Neto sólo campaña (90%) | 3.426,69 | 10.280,07 |
| Neto final (91,5%) | 2.912,68 | 8.738,04 |
| **`q-` impreso bajo el producto** | **30.840,19** | **92.520,57** |
| Descuento real de la línea | 31.354,20 | 94.062,60 |

- **`q-` agregado / pie:** `94.062,60 − 92.520,57 = ` **1.542,03**
- **Suma de todo lo impreso:** `92.520,57 + 1.542,03 = ` **94.062,60** = el
  descuento real del pedido en Odoo ✅
- **Total que le queda a la impresora:**
  `102.800,64 − 92.520,57 − 1.542,03 = ` **8.738,04** = el neto de Odoo ✅

Los **2 céntimos** entre el 1.542,01 de la línea de Odoo y el 1.542,03 impreso
son redondeo por línea (3 × 0,0065). No descuadran nada: la identidad se cierra
contra el descuento real (`Σ(bruto − neto final) × qty`), que es lo que la
impresora compara en el `199`, no contra el importe nominal de la línea de
descuento del POS.

> **Nota (C3, revisión formal):** este ejemplo es del camino **OFF**
> (`native_global_discount_line` en `false`, el % de campaña se compone con el
> global vía `composeDiscountPercent` y queda escrito en `line.discount`). El
> 1.542,03 de aquí sigue siendo el valor CORRECTO tras el fix de C3 —el bug de
> 1 céntimo que C3 corrige vivía SÓLO en el camino **ON**, donde
> `_convertOrderForDriver` recomputaba una tasa cascada por línea en vez de
> usar el monto exacto ya disponible (`globalDiscountAmount`). En el camino
> OFF, `globalOnlyDiscountAmount` se sigue derivando como
> `global_discount_amount (histórico) − Σ(q- de campaña)`, que para este caso
> da exactamente 1.542,03 — sin cambios. Ver el bloque C3 más arriba y el
> comentario junto a `globalOnlyDiscountAmount` en `_convertOrderForDriver`
> para el detalle completo, incluida la variante que se evaluó y se descartó
> por no reproducir este mismo 1.542,03.

## Implementación

### `l10n_ve_mf_base/static/src/core/DiscountMath.js`

Módulo puro con **dos** funciones:

- `composeDiscountPercent(a, b)` — composición **multiplicativa** de dos
  porcentajes: `100 − ((100−a)(100−b))/100`, redondeado a 2 decimales.
  **Único llamador hoy: `PosStore._applyGlobalDiscountBeforeValidation`.**
  `_convertOrderForDriver` **no** la usa: allí la cascada se hace sobre
  **precios**, con dos aplicaciones sucesivas de `_applyDiscount`, que es
  aritméticamente equivalente. (Versiones anteriores de este documento y el
  docblock del módulo decían que la usaban los dos; era falso y quedó
  corregido.)
- `computeLineDiscountAmount({ grossUnitPrice, netUnitPrice, quantity, rounding })`
  — el MONTO en Bs que una línea descuenta, es decir el argumento del `q-`.
  La usa `PosStore._convertOrderForDriver` para poblar `discount_amount`.

Ya **no** expone lógica de clamp de porcentaje (`MAX_LINE_DISCOUNT_PCT` y
`clampLineDiscountPercent` fueron eliminados): con un monto exacto no hay techo
de 99,99% que acotar.

Vive en `l10n_ve_mf_base/core` y no dentro de PosStore por dos razones:

1. **Una sola implementación de cada fórmula.** Las dos son aritmética que
   decide si el ticket impreso cuadra con lo que cobra Odoo, y ambas tienen un
   camino distinto según el flag `native_global_discount_line`. Duplicarlas
   dentro de PosStore.js es exactamente cómo divergirían.
2. **Testeabilidad.** El bundle `web.qunit_suite_tests` carga
   `web.assets_backend` (donde vive este módulo) pero **no**
   `point_of_sale._assets_pos` (donde vive PosStore.js). Poniéndolas aquí, los
   tests QUnit ejercitan las funciones de producción y no una copia espejo.

### `PosStore.js` — `_convertOrderForDriver`

Cada elemento de `lines` conserva todo lo que ya tenía (incluido `price_unit`
neto, que siguen consumiendo NC/ND) y suma dos campos:

- `gross_price_unit` — precio unitario **bruto**, antes de cualquier descuento.
- `discount_amount` — el monto **exacto** en Bs que esa línea descuenta,
  calculado por `computeLineDiscountAmount()`:

  ```
  max(0, round(bruto × cantidad) − round(neto × cantidad))
  ```

  El orden importa. **No** es `round((bruto − neto) × cantidad)`: con cantidad
  fraccionaria las dos formas pueden diferir en un céntimo. Ejemplo real
  (1,5 kg a 5,00 Bs con 5% de descuento, neto 4,75):

  | | fórmula | resultado | total de línea que queda |
  |---|---|---|---|
  | ✗ anterior | `round((5,00 − 4,75) × 1,5)` = `round(0,375)` | **0,38** | 7,50 − 0,38 = **7,12** |
  | ✓ actual | `round(7,50) − round(7,125)` = `7,50 − 7,13` | **0,37** | 7,50 − 0,37 = **7,13** |

  Odoo cobra `round(neto × cantidad)` = **7,13**, y ese número es el que
  alimenta los montos de pago `2XX` que la impresora compara contra su propio
  cálculo en el cierre `199`. Con la forma ✗ el céntimo de diferencia basta para
  que el `199` salga con NAK. Con la forma ✓ la identidad
  `round(bruto × qty) − descuento === round(neto × qty)` se cumple **siempre,
  por construcción**. Con cantidad entera ambas formas coinciden.

  El `max(0, …)` es una guarda defensiva: nunca debe poder salir negativo.

El `neto` ya contempla los dos estados del flag `native_global_discount_line`,
para que **el ticket impreso sea idéntico en ambos**:

- **Con `preAppliedMeta`** (flag en OFF): `_applyGlobalDiscountBeforeValidation`
  ya reescribió `line.discount` con el % **final** (campaña ya compuesta con
  global). Se usa tal cual, sin recalcular.
- **Sin `preAppliedMeta`** (flag en ON): la línea nativa de descuento de Odoo
  sigue presente como producto aparte, así que se deriva `globalRate` (como ya
  se hacía) y se aplica en cascada sobre el neto de campaña — dos
  `_applyDiscount` sucesivos, aritméticamente equivalentes a la composición
  multiplicativa de `composeDiscountPercent()`, aunque **no** llamen a esa
  función.

A nivel de orden se agrega `line_discount_via_q` (el interruptor) y, por la
separación campaña/global, `global_only_discount_amount` /
`global_only_discount_rate`.
`global_discount_rate` / `global_discount_amount` / `global_clamped` **se siguen
calculando y enviando igual que antes**, sin cambios, por compatibilidad y
porque NC/ND los usan — ver "Campos nuevos (y por qué no se pisaron los
viejos)".

> ⚠ `discount_amount` ya **no** es el descuento total de la línea: lleva
> únicamente la porción de campaña. El total real de la línea sigue reflejado en
> `price_unit` (neto).

### `TfhkaDriver.js` — `printInvoice`

1. Con `line_discount_via_q` en ON, el ítem se registra con
   `line.gross_price_unit`, con *fallback* a `line.price_unit` si el campo nuevo
   no viniera. Con el interruptor en OFF se usa siempre `price_unit`.
2. **Antes** de registrar el ítem se comprueba que el precio bruto cabe en
   `config.max_amount_int`. Si no cabe, esa línea se **degrada completa**:
   vuelve a `price_unit` (neto) y **no** emite `q-`. El nombre se acumula en
   `line_gross_price_overflow_lines`.
3. Si el interruptor está en ON y `discount_amount > 0`, se emite
   `q-` + `_formatAmount(monto, config.disc_int, config.disc_decimal)`
   **inmediatamente después** del comando del ítem, previa verificación de que
   el monto cabe en `config.disc_int` dígitos enteros.
4. Las líneas cuyo MONTO desborda se devuelven en
   `line_discount_overflow_lines`; las que degradaron por PRECIO, en
   `line_gross_price_overflow_lines`. Cada lista levanta su propio pop-up en el
   `PosStore`, con un texto distinto (la consecuencia visible no es la misma).

### `TfhkaDriver.js` — `_amountFitsField(num, intPart, decPart)`

Helper nuevo. Formatea con `_formatAmount` y comprueba que la cadena mide
exactamente `intPart + decPart`. Reemplaza las comparaciones crudas del tipo
`valor < 10 ** intPart`, que dejan pasar valores del borde (ver la sección
"Guarda de desbordamiento" más arriba).

### `TfhkaDriver.js` — `_appendFooterInfo(commands, orderData)`

El parámetro `skipDiscountInfo` **fue eliminado** (y con él `skipAmountLine` en
`_appendDiscountInfoLine`). Existía para suprimir la línea agregada del pie en
la factura cuando el descuento salía por línea vía `q-`; al separar campaña de
global esa línea dejó de ser redundante —representa el descuento sobre el TOTAL
del pedido— y ningún llamador pasaba ya `true`. Los tres documentos emiten la
línea de monto cuando hay monto que mostrar.

`printInvoice` con el interruptor en ON pasa una **copia** de `orderData` con
`global_discount_amount`/`_rate` sustituidos por la porción "solo global"; NC y
ND siguen llamando con la orden tal cual, de modo que **no cambian en
absoluto**.

`_appendDiscountInfoLine` sigue emitiendo el aviso
`DESC. GLOBAL EXCEDIO SUBTOTAL` cuando `global_clamped` es true, tomando el
primer índice `iXX` libre — ahora **incluso si el monto agregado es 0** (pedido
cuyas líneas ya estaban todas al 100% de campaña), caso en el que antes el
`return` temprano se lo llevaba por delante.

> Corrección de documentación: el docstring de `_appendDiscountInfoLine` decía
> "Solo se invoca para facturas", lo cual **nunca fue cierto** —
> `_appendFooterInfo` siempre se llamó también desde `printCreditNote` y
> `printDebitNote`, de modo que la línea "DESC. GLOBAL" sí salía en NC/ND. El
> docstring quedó corregido. El comportamiento de NC/ND se preservó tal cual
> está hoy en producción (no se "arregló" nada ahí a propósito).

## ⚠ Riesgo abierto: NO validado contra impresora física

**El camino `q-` por línea no ha sido probado contra una impresora TFHKA real.**
Todo lo anterior está verificado contra el manual y contra la construcción de
tramas en tests con `MockSerialConnection`, que es un mock: siempre responde ACK
y no modela el comportamiento interno del equipo. **Por eso el interruptor nace
en OFF.**

Lo que queda por confirmar con hardware real antes de encender el flag en un
cliente:

1. **Que la impresora acepta `q-` después de un ítem positivo (ACK, no NAK).**
   Es el supuesto central que resta. El comando en sí ya se usa en producción en
   este proyecto (NC/ND), pero **tras el subtotal**, no tras un ítem. El único
   experimento previo de "llevar el descuento a la impresora" (ítem con precio
   negativo) fue rechazado con NAK y dejó la transacción trabada en `STS1=0x61`.
2. **Que el renglón `DESC` sale bajo el producto correcto** y con la tasa de
   impuesto de ese ítem, tal como describe el desglose de la pág. 35.
3. **Que no hay NAK al combinar `q-` por línea con IGTF / pagos en divisa**
   (Flag 50 = 01, cierre con `199`). Este riesgo es **preexistente e
   independiente** del descuento: el manual no documenta restricciones, pero
   tampoco muestra el caso combinado.
4. **Que combinar `q-` por línea CON un `q-` agregado tras el subtotal en el
   mismo documento devuelva ACK.** Es el punto nuevo que introduce la
   separación campaña/global. Cada mecanismo por separado ya está en
   producción (`q-` tras el subtotal en NC/ND), pero **el manual no muestra un
   ejemplo con los dos a la vez**. Verificar además **cómo reparte la
   impresora el descuento agregado entre los buckets de tasa de impuesto**: lo
   hace proporcionalmente al subtotal de cada bucket, igual que Odoo prorratea
   el global sobre el neto de cada línea, pero el redondeo de ese reparto es
   interno del equipo y podría diferir en céntimos del de Odoo en un pedido con
   varias tasas (exento + G16%, por ejemplo). Probar con un pedido mixto de al
   menos dos tasas y comparar el `SUBTTL` y cada bucket contra Odoo.
5. **Que con cantidad ≠ 1 la impresora resta el monto del TOTAL de la línea y
   no del precio unitario.** El manual **no trae ningún ejemplo de `q-` con
   cantidad distinta de 1**: todos los casos de la Tabla 29 registran una sola
   unidad. Que el descuento por monto se aplique al total de la línea es la
   lectura razonable (y la que hace el código: `discount_amount` es el monto de
   la línea completa), pero **no está documentada explícitamente**. Si la
   impresora lo interpretara como unitario, una línea de 3 unidades saldría
   descontada tres veces y el `199` sería rechazado. Es la **primera** prueba
   que hay que hacer con hardware real, junto con el punto 1: una línea con
   cantidad 2 o 3 y descuento, verificando que el `SUBTTL` impreso coincide con
   el total de Odoo.

### Lo que ya NO es un riesgo

El **descuadre aritmético entre Odoo y la impresora por el descuento en sí**
quedó eliminado. Con `p-` la impresora tenía que calcular ella misma el neto a
partir de un porcentaje de 2 decimales, y cualquier diferencia de redondeo
(orden de las operaciones, cantidad > 1, un `line.discount` con más de 2
decimales) podía hacer que los montos `2XX` de pago —calculados en Odoo— no
cuadraran con el cálculo interno del equipo y que el cierre `199` fuera
rechazado con NAK. Con `q-` la impresora **no hace ninguna cuenta**: recibe un
monto ya redondeado con la misma precisión de moneda que usó Odoo para los
pagos, y sólo lo resta.

## Tests

En `l10n_ve_pos_mf/static/src/tests/tfhka_driver_tests.js`:

- `q-` se emite **justo después** de su ítem, y el ítem lleva el precio bruto.
- El formato del monto **SÍ depende del Flag 21** (casos `00`, `02` y `30`; el
  `30` produce una trama visiblemente más larga) — a diferencia de `p-`, que no
  dependía.
- Una línea con `discount_amount = 0` **o sin el campo** no genera ningún `q-`.
  Con cantidad > 1 el monto emitido es el **total de la línea**, no el unitario.
- Una línea al **100% de descuento** se expresa como monto exacto, sin recorte.
- **Cantidad fraccionaria**: con 1,5 unidades a 5,00 con 5% de descuento el
  `q-` lleva 0,37 (no 0,38) y se verifica la identidad
  `round(bruto × qty) − q- == round(neto × qty)`.
- **Desbordamiento del MONTO**: un monto que no cabe en `config.disc_int` NO
  emite `q-`, el ítem se imprime igual a precio bruto, y el nombre se devuelve
  en `line_discount_overflow_lines`. Incluye el **caso del borde**
  (`9.999.999,996`, que la comparación cruda dejaba pasar).
- **Desbordamiento del PRECIO BRUTO**: una línea cuyo bruto no cabe en
  `config.max_amount_int` se imprime con `price_unit` (neto) y sin `q-`, el
  resto de las líneas no se ve afectado, y el nombre se devuelve en
  `line_gross_price_overflow_lines`. El test comprueba además que **todos** los
  comandos de ítem conservan el ancho de campo del Flag 21.
- **Interruptor en OFF**: el ítem va con `price_unit` (neto), no hay ningún
  `q-` por línea, y vuelve la línea agregada "DESC. GLOBAL" del pie.
- `composeDiscountPercent` y `computeLineDiscountAmount` (funciones reales de
  producción, no copias espejo); la segunda con cantidad entera **y**
  fraccionaria, más las guardas de argumentos ausentes.
- `_appendFooterInfo`: la línea agregada se emite **siempre** (un tercer
  argumento sobrante ya no la suprime — el parámetro `skipDiscountInfo` fue
  eliminado), y desaparece sólo cuando no hay monto. El aviso "EXCEDIO
  SUBTOTAL" sobrevive incluso con el monto agregado en 0.
- **Separación campaña / global** (cuatro tests nuevos):
  - línea CON campaña y global activo: su `q-` lleva **sólo** el monto de
    campaña, el compuesto no aparece en ninguna trama, el global sale como `q-`
    agregado tras el subtotal y la línea "DESC. GLOBAL" del pie muestra esa
    misma porción;
  - línea SIN campaña bajo un global: **no** lleva `q-` propio y su descuento
    entero aparece una sola vez, en el agregado;
  - **escenario mixto** (una línea con campaña + otra sin, mismo global):
    verifica la identidad `Σ(q- por línea) + agregado == descuento real de
    Odoo` y que `bruto − todo lo descontado == el neto que cobra Odoo`;
  - **caso real de campo** (3 × 34.266,88 al 90% + global ≈15%): reproduce los
    números de la tabla de la sección "Caso numérico de referencia".
- **No regresión de NC**: con una línea que trae `gross_price_unit` y
  `discount_amount`, y con `line_discount_via_q` incluso en ON, la NC sigue
  usando `price_unit`, emite **un solo** `q-` (el agregado, después del
  subtotal, no pegado al ítem) y conserva la línea "DESC. GLOBAL" del pie.

> Estos tests **no se ejecutaron en navegador**: este entorno no tiene uno y
> QUnit necesita la página `/web/tests` de Odoo. Queda pendiente que un humano
> los corra. La lógica sí fue ejecutada fuera de QUnit con un arnés en Node
> (`/tmp/sc-harness`, regenerable con su `rebuild.sh`) que copia los archivos
> fuente reales — driver, `MockSerialConnection`, `DiscountMath` y el propio
> archivo de tests — reescribiendo sólo las rutas de import de Odoo, y que usa
> la implementación literal de `roundPrecision` del Odoo del contenedor. Estado
> actual: **47 tests, 259 aserciones, 0 fallos**.
