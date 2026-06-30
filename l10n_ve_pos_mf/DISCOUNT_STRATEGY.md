# Global Discount vs Line Discount in Fiscal Printing (TFHKA)

## Context

This note compares how discounts are calculated in POS vs how TFHKA applies fiscal commands, based on real tests in this project.

Current config observed during tests:

- Tax model: price + tax (tax is not included in product price)
- Main VAT rate: 16%
- Fiscal printer integration: Web Serial (`l10n_ve_pos_mf`)

## Why totals differ

Even with "10% discount" in both flows, totals differ because the discount is applied at different stages.

### Case 1: Line discount

- Product base: 100.00
- Line discount 10%: -10.00 on base
- Tax base becomes: 90.00
- VAT 16%: 14.40
- Total: 104.40

### Case 2: Global discount via `q-`

- Product base: 100.00
- VAT 16%: 16.00
- Subtotal: 116.00
- `q-10.00` discount applied after subtotal
- Total: 106.00

Result: line discount and global discount are not equivalent with this tax setup.

## What was tested

### Option A tested (negative lines as fiscal items)

Implemented temporarily:

- Send negative discount line as normal item command (instead of `q-`)

Observed on real printer:

- Command like ` -000000100000001000|DISC|Descuento` was rejected (`NAK`)
- Transaction got stuck in `STS1=0x61`
- Recovery with `9`/`199` did not complete reliably

Conclusion: this firmware/model does not accept negative item lines in this invoice flow.

### Rollback performed

System was returned to previous stable behavior:

- Negative POS lines are not sent as items
- Global discount is sent with `q-`
- Tests are green with this behavior

## Current behavior (stable)

- Line discounts: converted to net unit price before sending line
- Global discounts: mapped to fiscal `q-` absolute amount
- This is protocol-safe for current printer/firmware, but arithmetic differs from line discount by design

## Decision options for team

### Option 1: Keep current approach (`q-` for global discounts)

Pros:

- Works with current printer firmware
- Stable and already tested

Cons:

- Global discount totals differ from line discount totals in tax-exclusive mode
- User confusion unless clearly explained

When to choose:

- Priority is hardware compatibility and low risk

### Option 2: Functional policy - disable global discount in POS UI

Pros:

- Enforces a single fiscal-consistent discount method (line discount)
- Avoids user confusion and accounting disputes

Cons:

- Changes cashier workflow
- Requires product/process update and user training

When to choose:

- Priority is mathematical consistency in tax handling

### Option 3: Keep global discount but with explicit rule and training

Pros:

- No UI restriction
- Keeps both tools available

Cons:

- Requires clear SOP: line discount and global discount are not equivalent
- Still needs support for user questions

When to choose:

- Business wants flexibility and accepts non-equivalent totals

## Recommended path

For production robustness on current hardware:

1. Keep current protocol implementation (`q-` for global discount)
2. Decide with stakeholders whether to:
   - Disable global discount (preferred for consistency), or
   - Keep it with explicit user guidance
3. Add a short help note in POS docs/training: "Line discount affects tax base; global discount (`q-`) is applied after subtotal."

## Checklist for final team decision

- Is legal/accounting policy expecting global discount to reduce tax base?
- Is cashier workflow acceptable with line-discount-only policy?
- Do we need to preserve legacy behavior from IoT/old deployments?
- Should the POS UI warn when using global discount in tax-exclusive mode?

If all answers prioritize consistency over flexibility, implement policy: line discounts only.
