# Global Discount vs Line Discount in Fiscal Printing (TFHKA)

## Context

This note compares how discounts are calculated in POS vs how TFHKA applies fiscal commands, based on real tests in this project.

Current config observed during tests:

- Tax model: price + tax (tax is not included in product price)
- Main VAT rate: 16%
- Fiscal printer integration: Web Serial (`l10n_ve_pos_mf`)

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
