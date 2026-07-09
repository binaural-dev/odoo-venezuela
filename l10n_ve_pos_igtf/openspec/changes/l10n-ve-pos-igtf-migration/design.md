# Design: l10n_ve_pos_igtf Odoo 17→19 Migration

## 1. Architecture Overview

The migration follows the **compat-wrapper** pattern proven in `l10n_ve_pos`.

- **Core principle**: Patch `PosOrder.prototype` and `PosPayment.prototype` (Odoo 19 classes), not the legacy `Order`/`Payment` classes.
- **Wrapper strategy**: Keep the existing IGTF logic almost verbatim by adding thin wrapper methods that bridge Odoo 17 snake_case API → Odoo 19 camelCase API.
- **Foreign currency math**: Re-use `l10n_ve_pos` helpers (`localToForeign`, `foreignToLocal`, `get_foreign_total_with_tax`, etc.) — do NOT duplicate conversion logic.
- **File dependency tree**:

```
  l10n_ve_pos (already migrated)
       │
       ├── pos_order.js ──→ provides localToForeign, get_foreign_total_with_tax, etc.
       │
       └── payment_model.js ──→ provides set_foreign_amount, get_foreign_amount, etc.
       │
  l10n_ve_pos_igtf
       │
       ├── order_model.js ──→ patches PosOrder, calls l10n_ve_pos helpers + compat wrappers
       ├── payment_model.js ──→ patches PosPayment, adds igtf_amount / foreign_igtf_amount fields
       ├── payment_screen.js ──→ patches PaymentScreen, triggers update_igtf()
       ├── payment_status.js ──→ patches PaymentScreenStatus, formats IGTF display values
       ├── pos_payment.py ──→ overrides _create_payment_moves for IGTF journal entries
       └── XML views ──→ inherits from O19 core views (IDs verified stable O17→O19)
```

## 2. Import Strategy

### order_model.js
```js
// OLD (O17)
import { Order, Payment } from "@point_of_sale/app/store/models";

// NEW (O19)
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { PosPayment } from "@point_of_sale/app/models/pos_payment";
```
Patch target changes from `Order.prototype` → `PosOrder.prototype`.

### payment_model.js
```js
// OLD (O17)
import { Payment } from "@point_of_sale/app/store/models";

// NEW (O19)
import { PosPayment } from "@point_of_sale/app/models/pos_payment";
```
Patch target changes from `Payment.prototype` → `PosPayment.prototype`.

### payment_screen.js
No model import changes needed (already imports `PaymentScreen` from the correct O19 path). No action.

### payment_status.js
```js
// OLD (O17)
import { usePos } from "@point_of_sale/app/store/pos_hook";

// NEW (O19)
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
```

## 3. Wrapper Methods

Add these wrappers to the `PosOrder` patch in `order_model.js` so existing IGTF logic continues to work:

```js
patch(PosOrder.prototype, {
  // ... existing IGTF methods ...

  // --- Compat wrappers (O17 → O19) ---
  get_paymentlines() {
    return this.payment_ids ? Array.from(this.payment_ids) : [];
  },

  get_total_with_tax() {
    return Number(
      this.totalDue ??
      (typeof super.get_total_with_tax === "function" ? super.get_total_with_tax() : 0)
    ) || 0;
  },

  get_due() {
    return Number(
      this.remainingDue ??
      (typeof super.get_due === "function" ? super.get_due() : 0)
    ) || 0;
  },

  add_paymentline(payment_method) {
    // Delegate to O19 API; preserve return value
    return this.addPaymentline(payment_method);
  },

  select_paymentline(line) {
    this.selectPaymentline(line);
  },

  assert_editable() {
    if (typeof this.assertEditable === "function") {
      this.assertEditable();
    }
    // O19 may have renamed or removed this; guard with typeof
  },

  electronic_payment_in_progress() {
    if (typeof this.electronicPaymentInProgress === "function") {
      return this.electronicPaymentInProgress();
    }
    return false;
  },

  get_selected_paymentline() {
    return this.selectedPaymentLine ?? this.selected_paymentline ?? null;
  },
});
```

**Rationale**: The 346-line `update_igtf()` and `add_paymentline_without_igtf()` rely on `get_paymentlines()`, `get_total_with_tax()`, `get_due()`, `add_paymentline()`, `select_paymentline()`, `assert_editable()`, `electronic_payment_in_progress()`. Wrapping them once avoids scattering defensive code across 200+ lines of business logic.

## 4. Rename Table

| File | Old (O17) | New (O19) | Notes |
|------|-----------|-----------|-------|
| `order_model.js` | `Order` class | `PosOrder` class | Import + patch target |
| `order_model.js` | `Payment` class | `PosPayment` class | Import only (for `new Payment`) |
| `order_model.js` | `patch(Order.prototype, {...})` | `patch(PosOrder.prototype, {...})` | |
| `order_model.js` | `this.get_paymentlines()` | `this.payment_ids` (getter) | Wrapped; internal code can also use getter directly |
| `order_model.js` | `this.get_total_with_tax()` | `this.totalDue` | Wrapped |
| `order_model.js` | `this.get_due()` | `this.remainingDue` | Wrapped |
| `order_model.js` | `this.add_paymentline(method)` | `this.addPaymentline(method)` | Wrapped |
| `order_model.js` | `this.select_paymentline(line)` | `this.selectPaymentline(line)` | Wrapped |
| `order_model.js` | `this.assert_editable()` | `this.assertEditable()` | Wrapped with typeof guard |
| `order_model.js` | `this.electronic_payment_in_progress()` | `this.electronicPaymentInProgress()` | Wrapped with typeof guard |
| `order_model.js` | `this.selected_paymentline` | `this.selectedPaymentLine` | Wrapped |
| `order_model.js` | `payment.cid` | `payment.uuid` | Used in `bi_payments.push(payment.cid)` → `payment.uuid` |
| `order_model.js` | `payment.payment_method` | `payment.payment_method_id` | Used in `payment.payment_method.apply_igtf` → `payment.payment_method_id?.apply_igtf` |
| `order_model.js` | `payment.get_amount()` | `payment.getAmount()` | l10n_ve_pos already adds `get_amount()` alias |
| `order_model.js` | `payment.set_amount(x)` | `payment.setAmount(x)` | l10n_ve_pos already overrides `setAmount()` |
| `order_model.js` | `payment.get_foreign_amount()` | `payment.get_foreign_amount()` | **Unchanged** — l10n_ve_pos provides this helper |
| `order_model.js` | `payment.set_foreign_amount(x)` | `payment.set_foreign_amount(x)` | **Unchanged** — l10n_ve_pos provides this helper |
| `payment_model.js` | `patch(Payment.prototype, {...})` | `patch(PosPayment.prototype, {...})` | |
| `payment_status.js` | `formatCurrency(value, 'Product Price')` | `formatCurrency(value)` | Remove 2nd arg everywhere |
| `payment_status.js` | `this.props.order.get_paymentlines()` | `Array.from(this.props.order.payment_ids \|\| [])` | Or use wrapper |
| `payment_status.js` | `this.props.order.get_total_with_tax()` | `this.props.order.totalDue` | Or use wrapper |
| `payment_screen.js` | `this.pos.get_order()` | `this.currentOrder` | Already partially used; replace remaining occurrences |

## 5. add_paymentline_without_igtf Rewrite

**Current (O17) — lines 319-344 in order_model.js:**
```js
add_paymentline_without_igtf(payment_method) {
    this.assert_editable();
    if (this.electronic_payment_in_progress()) {
        return false;
    } else {
        var newPaymentline = new Payment(
            { env: this.env },
            { order: this, payment_method: payment_method, pos: this.pos },
        );
        this.paymentlines.add(newPaymentline);
        this.select_paymentline(newPaymentline);
        if (this.pos.config.cash_rounding) {
            this.selected_paymentline.set_amount(0);
        }
        newPaymentline.set_foreign_amount(
            this.get_foreign_due() - this.get_foreign_igtf_amount(),
            true,
        );
        newPaymentline.set_amount(this.get_due() - this.get_igtf_amount(), true);
        if (payment_method.payment_terminal) {
            newPaymentline.set_payment_status("pending");
        }
        return newPaymentline;
    }
}
```

**New (O19) — step-by-step transformation:**

1. **Remove `new Payment(...)`**: In O19, payment records are created via the model registry:
   ```js
   const newPaymentline = this.models["pos.payment"].create({
       pos_order_id: this,
       payment_method_id: payment_method,
       amount: 0,
   });
   ```
   The relationship to the order is auto-established by `pos_order_id`.

2. **Remove `this.paymentlines.add(...)`**: O19's `create()` already inserts into the relational set.

3. **Remove `this.select_paymentline(...)`**: Use wrapper `this.selectPaymentline(newPaymentline)`.

4. **Cash rounding check**: `this.pos.config.cash_rounding` still exists; if true, set amount to 0 via `newPaymentline.setAmount(0)`.

5. **Set foreign amount**: Call `newPaymentline.set_foreign_amount(...)` (provided by l10n_ve_pos payment_model.js patch). The `true` second arg in O17 was a `force` flag; l10n_ve_pos's `set_foreign_amount` only takes one arg and computes local amount internally. Verify if the `true` semantics are needed — in l10n_ve_pos, `set_foreign_amount` already handles the conversion and sets both `foreign_amount` and `amount`.

6. **Set local amount**: After `set_foreign_amount`, the local `amount` is already set by l10n_ve_pos logic. However, `add_paymentline_without_igtf` needs amount = `due - igtf`. So we should set amount explicitly AFTER set_foreign_amount:
   ```js
   const amountWithoutIgtf = this.get_due() - this.get_igtf_amount();
   newPaymentline.setAmount(amountWithoutIgtf);
   ```
   This triggers l10n_ve_pos `setAmount()` → `_recomputeForeignFromLocal()`, which will recompute `foreign_amount` from the new local amount. That's acceptable because `add_paymentline_without_igtf`'s goal is to pay the due minus IGTF.

7. **Payment terminal**: `payment_method.payment_terminal` still exists; set status via `newPaymentline.setPaymentStatus("pending")` if that method exists, else check O19 core API.

**Resulting body (draft):**
```js
add_paymentline_without_igtf(payment_method) {
    this.assertEditable();
    if (this.electronicPaymentInProgress && this.electronicPaymentInProgress()) {
        return false;
    }
    const newPaymentline = this.models["pos.payment"].create({
        pos_order_id: this,
        payment_method_id: payment_method,
        amount: 0,
    });
    this.selectPaymentline(newPaymentline);
    if (this.pos.config.cash_rounding) {
        newPaymentline.setAmount(0);
    }
    // Compute amount excluding IGTF
    const due = Number(this.remainingDue ?? 0) || 0;
    const igtf = this.get_igtf_amount ? this.get_igtf_amount() : 0;
    const amountWithoutIgtf = due - igtf;
    newPaymentline.setAmount(amountWithoutIgtf);
    // Core setAmount triggers l10n_ve_pos _recomputeForeignFromLocal()
    // which sets foreign_amount correctly.
    if (payment_method.payment_terminal && typeof newPaymentline.setPaymentStatus === "function") {
        newPaymentline.setPaymentStatus("pending");
    }
    return newPaymentline;
}
```

**Alternative (safer)**: Keep `add_paymentline_without_igtf` largely untouched but call wrappers:
```js
add_paymentline_without_igtf(payment_method) {
    this.assert_editable();          // wrapper → assertEditable()
    if (this.electronic_payment_in_progress()) {
        return false;
    }
    // --- O19 creation ---
    const newPaymentline = this.models["pos.payment"].create({
        pos_order_id: this,
        payment_method_id: payment_method,
        amount: 0,
    });
    // --- rest unchanged via wrappers ---
    this.select_paymentline(newPaymentline);   // wrapper
    if (this.pos.config.cash_rounding) {
        this.get_selected_paymentline().set_amount(0); // wrapper
    }
    newPaymentline.set_foreign_amount(
        this.get_foreign_due() - this.get_foreign_igtf_amount(),
        true,
    );
    newPaymentline.set_amount(this.get_due() - this.get_igtf_amount(), true);
    if (payment_method.payment_terminal) {
        newPaymentline.set_payment_status("pending");
    }
    return newPaymentline;
}
```
This preserves the O17 call style and defers O19 specifics to wrappers / l10n_ve_pos helpers.

## 6. update_igtf() Migration

`update_igtf()` (lines 37-223) is mostly **mechanical renames**.

### Mechanical changes (search-and-replace):
- `this.get_paymentlines()` → `this.get_paymentlines()` (wrapper handles it; or inline `Array.from(this.payment_ids || [])`)
- `payment.payment_method.apply_igtf` → `payment.payment_method_id?.apply_igtf`
- `payment.cid` → `payment.uuid`
- `payment.amount` → `payment.amount` (unchanged in O19)
- `payment.get_foreign_amount()` → `payment.get_foreign_amount()` (unchanged — l10n_ve_pos helper)
- `payment.set_include_igtf(bool)` → `payment.set_include_igtf(bool)` (unchanged — our own patch)
- `payment.set_igtf_amount(amt)` → `payment.set_igtf_amount(amt)` (unchanged — our own patch)
- `payment.set_foreign_igtf_amount(amt)` → `payment.set_foreign_igtf_amount(amt)` (unchanged — our own patch)
- `this.get_total_with_tax()` → `this.get_total_with_tax()` (wrapper)
- `this.get_foreign_total_with_tax()` → `this.get_foreign_total_with_tax()` (l10n_ve_pos helper, unchanged)
- `this.get_due()` → `this.get_due()` (wrapper)
- `this.get_foreign_due()` → `this.get_foreign_due()` (l10n_ve_pos helper, unchanged)
- `this.get_igtf_amount()` → `this.get_igtf_amount()` (our own patch, unchanged)
- `this.get_foreign_igtf_amount()` → `this.get_foreign_igtf_amount()` (our own patch, unchanged)
- `this.get_total_without_igtf()` → `this.get_total_without_igtf()` (our own patch, unchanged)
- `this.get_foreign_total_without_igtf()` → `this.get_foreign_total_without_igtf()` (our own patch, unchanged)

### Logic changes:
- **Line 146-148**: `payment.amount > this.get_total_with_tax()` — `payment.amount` is still a number in O19. Safe.
- **Line 166-169**: `bi_igtf >= this.get_total_without_igtf()` — safe.
- **No behavioral changes** to rounding, filtering, or IGTF percentage application.

**Approach**: Add the wrappers first, then run a minimal search/replace pass for `payment_method` → `payment_method_id` and `cid` → `uuid`. The rest stays identical.

## 7. payment_status.js Changes

Current file: 96 lines. Changes needed:

### formatCurrency fix
Remove `'Product Price'` second argument from ALL `formatCurrency` and `formatForeignCurrency` calls.

**Lines to change:**
- Line 18: `this.env.utils.formatCurrency(this.props.order.get_igtf_amount(), 'Product Price')` → `this.env.utils.formatCurrency(this.props.order.get_igtf_amount())`
- Line 21: `this.env.utils.formatCurrency(this.props.order.get_bi_igtf(), 'Product Price')` → `this.env.utils.formatCurrency(this.props.order.get_bi_igtf())`
- Line 24: `this.env.utils.formatForeignCurrency(..., 'Product Price')` → `this.env.utils.formatForeignCurrency(...)`
- Line 49: `formatCurrency(igtfAmount, 'Product Price')` → `formatCurrency(igtfAmount)`
- Line 57: `formatCurrency(igtfAmount, 'Product Price')` → `formatCurrency(igtfAmount)`

### Getter updates
- Line 27: `this.props.order.get_paymentlines()` → `Array.from(this.props.order.payment_ids || [])` or use wrapper if available on order instance.
- Line 38: Same as above.
- Line 53: `this.props.order.get_total_with_tax()` → `this.props.order.totalDue ?? this.props.order.get_total_with_tax()` (wrapper exists on order patch).
- Line 54: `this.props.order.get_rounding_applied()` → Verify O19 availability; may need wrapper.
- Line 61: `this.props.order.get_total_with_tax()` → same as line 53.
- Line 66: `this.props.order.get_foreign_total_with_tax()` → l10n_ve_pos helper, unchanged.
- Line 70: `this.props.order.get_paymentlines()` → same as line 27.
- Line 75: `this.props.order.get_total_with_tax()` → same as line 53.
- Line 78: `this.props.order.get_total_without_igtf()` → unchanged (our patch).
- Line 84: `this.props.order.get_total_with_tax()` → same as line 53.
- Line 86: `this.props.order.get_total_with_tax()` → same as line 53.
- Line 91: `this.props.order.get_total_without_igtf()` → unchanged.

**Defensive pattern to apply everywhere:**
```js
const total = Number(
    this.props.order?.totalDue ??
    (typeof this.props.order?.get_total_with_tax === "function" ? this.props.order.get_total_with_tax() : 0)
) || 0;
```

## 8. payment_screen.js Changes

Current file: 27 lines. Minimal changes.

- **Line 11**: `this.pos.get_order()` → `this.currentOrder` (already partially used at line 24). Change lines 11 and 18.
- **Line 11**: `this.pos.get_order().update_igtf()` → `this.currentOrder.update_igtf()`
- **Line 18**: `this.pos.get_order().update_igtf()` → `this.currentOrder.update_igtf()`
- **Line 24**: Already uses `this.currentOrder` — no change.

No method renames needed in this file; `addNewPaymentLine`, `updateSelectedPaymentline`, `toggleIsToInvoice` are all O19-compatible.

## 9. _create_payment_moves Adaptation

Current: 166 lines. Only `_create_payment_moves` needs changes.

### What to verify against O19 core
The method calls three `pos.session` helpers that may have changed in O19:
- `pos_session._update_amounts(oldAmounts, newAmounts, date)`
- `pos_session._credit_amounts(partialVals, amount, amountConverted)`
- `pos_session._debit_amounts(partialVals, amount, amountConverted)`

**Verification strategy:**
1. Search Odoo 19 core `addons/point_of_sale/models/pos_session.py` for `_update_amounts`, `_credit_amounts`, `_debit_amounts`.
2. If signatures changed, adapt the call sites (lines 54, 69, 88, 105, 138 in current file).
3. If methods were removed/renamed, use the O19 equivalent (likely `pos_session._get_amounts` or similar).

### Fallback strategy
If the helpers no longer exist:
- **Option A**: Inline the logic — compute `amount` and `amount_converted` directly using currency conversion helpers from `l10n_ve_pos` (same math as `_update_amounts`).
- **Option B**: Check if O19's `pos.session` provides new `_prepare_credit_line_vals` / `_prepare_debit_line_vals` methods and use those.
- **Option C**: Look at how O19 core `_create_payment_moves` (if it exists in `pos_payment.py`) handles amounts — copy that pattern.

### Specific lines to adapt
- **Lines 54-57**: `pos_session._update_amounts(...)` — verify signature.
- **Lines 69-86**: `pos_session._credit_amounts(...)` — verify signature and `foreign_debit`/`foreign_credit` key support.
- **Lines 88-103**: `pos_session._credit_amounts(...)` for IGTF line — same as above.
- **Lines 105-122**: `pos_session._credit_amounts(...)` for non-IGTF line — same as above.
- **Lines 138-155**: `pos_session._debit_amounts(...)` — verify signature.

### from_pos context
Add `from_pos=True` to the context when creating the account move:
```python
payment_move = (
    self.env["account.move"]
    .with_context(default_journal_id=journal.id, from_pos=True)
    .create({...})
)
```

## 10. View XML Verification

### pos_order.xml
```xml
<record id="view_pos_pos_form" model="ir.ui.view">
    <field name="inherit_id" ref="point_of_sale.view_pos_pos_form"/>
    ...
</record>
```
**Check**: `point_of_sale.view_pos_pos_form` must exist in O19. This is a stable core view ID; unlikely to change.

### pos_payment_method.xml
```xml
<record id="pos_payment_method_view_form" model="ir.ui.view">
    <field name="inherit_id" ref="point_of_sale.pos_payment_method_view_form"/>
    ...
</record>
```
**Check**: `point_of_sale.pos_payment_method_view_form` must exist in O19. Stable ID.

### pos_payment_views.xml
```xml
<record id="view_pos_payment_tree" model="ir.ui.view">
    <field name="inherit_id" ref="point_of_sale.view_pos_payment_tree"/>
    ...
</record>
<record id="view_pos_payment_form" model="ir.ui.view">
    <field name="inherit_id" ref="point_of_sale.view_pos_payment_form"/>
    ...
</record>
```
**Check**: Verify `point_of_sale.view_pos_payment_tree` and `point_of_sale.view_pos_payment_form` exist in O19.

### payment_status.xml (OWL template)
```xml
<t t-name="PaymentScreenStatus" t-inherit="point_of_sale.PaymentScreenStatus" ...>
```
**XPath checks**:
- `//div[hasclass('total')]` — verify O19 `PaymentScreenStatus` template still has a `div` with `total` class.
- `//div[hasclass('payment-status-change')]` — verify this class still exists in O19 template.

**Fallback**: If XPath fails, use more generic selectors or add `t-inherit-mode="extension"` with `position="replace"` on identifiable elements.

### payment_lines.xml (OWL template)
```xml
<t t-name="PaymentScreenPaymentLines" t-inherit="point_of_sale.PaymentScreenPaymentLines" ...>
    <xpath expr="//t[@t-foreach='props.paymentLines']" position="inside">
```
**Check**: O19 `PaymentScreenPaymentLines` template must still iterate over `props.paymentLines`. The `line` variable must still expose `line.include_igtf` and `line.selected`.

## 11. File-by-File Summary

| File | Action | What Changes | Est. Lines |
|------|--------|-------------|------------|
| `order_model.js` | Modify | Import path; patch target; add compat wrappers (~15 lines); mechanical renames (`cid`→`uuid`, `payment_method`→`payment_method_id`); rewrite `add_paymentline_without_igtf` creation block (~10 lines) | ~35 changed |
| `payment_model.js` | Modify | Import path; patch target (`Payment` → `PosPayment`) | ~2 changed |
| `payment_screen.js` | Modify | `this.pos.get_order()` → `this.currentOrder` on 2 lines | ~2 changed |
| `payment_status.js` | Modify | `formatCurrency(..., 'Product Price')` → `formatCurrency(...)` on 5 lines; `get_paymentlines()` → `payment_ids` on 3 lines; defensive getters for `get_total_with_tax()` | ~12 changed |
| `pos_payment.py` | Modify | Verify `_update_amounts`, `_credit_amounts`, `_debit_amounts` against O19 core; adapt signatures if needed; add `from_pos=True` context | ~10-30 changed (depends on core changes) |
| `payment_status.xml` | Verify | XPath selectors against O19 template | 0 if selectors match |
| `payment_lines.xml` | Verify | XPath `props.paymentLines` against O19 template | 0 if selector matches |
| `pos_order.xml` | Verify | View parent ID exists in O19 | 0 if ID exists |
| `pos_payment_method.xml` | Verify | View parent ID exists in O19 | 0 if ID exists |
| `pos_payment_views.xml` | Verify | View parent IDs exist in O19 | 0 if IDs exist |

**Total estimated changed lines**: ~60-80 across 4 JS + 1 Python file.

**New files**: None. All changes are modifications to existing files.

**Deleted files**: None.
