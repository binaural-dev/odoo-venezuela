# Tasks: l10n_ve_pos_igtf Odoo 17→19 Migration

**Approach**: Compat-wrapper migration. ~60-80 changed lines across 4 JS files, 1 Python method, and 5 XML verifications. Single PR.

---

## T1: Fix imports and patch targets

- [x] T1.1 `order_model.js`: change import path to `@point_of_sale/app/models/pos_order` and rename patch target `Order` → `PosOrder`; also import `PosPayment` from `@point_of_sale/app/models/pos_payment`
- [x] T1.2 `payment_model.js`: change import path to `@point_of_sale/app/models/pos_payment` and rename patch target `Payment` → `PosPayment`
- [x] T1.3 `payment_status.js`: ensure hook import resolves to `@point_of_sale/app/hooks/pos_hook`
- **Files**: `static/src/app/overrides/models/order_model.js`, `static/src/app/overrides/models/payment_model.js`, `static/src/app/overrides/screens/payment_status.js`
- **Spec**: frontend-imports.md
- **Est. lines**: 6

## T2: Add compat wrappers to PosOrder

- [x] T2.1 Add wrapper methods on `PosOrder` patch: `get_paymentlines()`, `get_total_with_tax()`, `get_due()`, `add_paymentline(...)`, `select_paymentline(...)`, `assert_editable()`, `electronic_payment_in_progress()`, `get_selected_paymentline()`
- [x] T2.2 Each wrapper delegates to the O19 API equivalent (see design §3 for the 8 bodies)
- **Files**: `static/src/app/overrides/models/order_model.js`
- **Spec**: frontend-api-wrappers.md
- **Est. lines**: 24

## T3: Mechanical renames across JS files

- [x] T3.1 `order_model.js` & `payment_status.js`: rename `payment_method` → `payment_method_id` (use `?.` guard on access)
- [x] T3.2 `order_model.js`: rename `cid` → `uuid`
- [x] T3.3 `payment_screen.js`: replace `this.pos.get_order()` → `this.currentOrder`
- **Files**: `static/src/app/overrides/models/order_model.js`, `static/src/app/overrides/screens/payment_status.js`, `static/src/app/overrides/screens/payment_screen.js`
- **Spec**: frontend-api-wrappers.md, frontend-igtf-calculation.md
- **Est. lines**: 8

## T4: Fix formatCurrency calls

- [x] T4.1 `payment_status.js`: remove the `'Product Price'` 2nd argument from every `formatCurrency` and `formatForeignCurrency` call
- **Files**: `static/src/app/overrides/screens/payment_status.js`
- **Spec**: frontend-display.md
- **Est. lines**: 4

## T5: Apply defensive getter patterns in payment_status.js

- [x] T5.1 Replace `get_paymentlines()` usage with `Array.from(this.currentOrder.payment_ids || [])`
- [x] T5.2 Replace `get_total_with_tax()` usage with `this.currentOrder.totalDue` guarded by `typeof ... === 'number'` fallback
- **Files**: `static/src/app/overrides/screens/payment_status.js`
- **Spec**: frontend-display.md
- **Est. lines**: 6

## T6: Rewrite add_paymentline_without_igtf

- [x] T6.1 Replace `new Payment(...)` + `this.paymentlines.add(...)` with `this.models["pos.payment"].create({...})`
- [x] T6.2 Use wrapper methods (`get_paymentlines`, `get_selected_paymentline`, `select_paymentline`) for the remaining calls in the method
- [x] T6.3 Verify the created payment object gets attached to `payment_ids` so downstream iteration works
- **Files**: `static/src/app/overrides/models/order_model.js`
- **Spec**: frontend-payment-creation.md
- **Est. lines**: 10

## T7: Verify and adapt _create_payment_moves (pos_payment.py)

- [x] T7.1 Compare `pos_payment.py` `_update_amounts`, `_credit_amounts`, `_debit_amounts` signatures against Odoo 19 core `pos.payment`
- [x] T7.2 Adapt the overrides if O19 signatures changed; keep behavior identical
- [x] T7.3 Inject `from_pos=True` in the context where the method is invoked from POS
- **Files**: `models/pos_payment.py`
- **Spec**: backend-payment-moves.md
- **Est. lines**: 6

## T8: Verify XML views and templates

- [x] T8.1 `views/pos_order.xml`: confirm parent view `inherit_id` ref exists in O19
- [x] T8.2 `views/pos_payment_method.xml`: confirm parent view exists in O19
- [x] T8.3 `views/pos_payment_views.xml`: confirm all parent view IDs referenced exist in O19
- [x] T8.4 `static/src/app/overrides/screens/payment_status.xml`: verify XPath selectors match the O19 template structure (and `payment_lines.xml` if present)
- **Files**: `views/pos_order.xml`, `views/pos_payment_method.xml`, `views/pos_payment_views.xml`, `static/src/app/overrides/screens/payment_status.xml`
- **Spec**: views-xml.md
- **Est. lines**: 0-10 (only if renames needed)

---

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~60-80 |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | exception-ok |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Full IGTF migration (T1-T8) | PR 1 | Single PR; under 400-line review budget |

## Implementation Order

T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8. Imports and patch targets must resolve before wrappers compile; renames must complete before the rewrite touches those identifiers; the `add_paymentline_without_igtf` rewrite depends on wrappers + renames being in place; backend and XML verification can run in parallel after the frontend lands but are ordered last for review coherence.