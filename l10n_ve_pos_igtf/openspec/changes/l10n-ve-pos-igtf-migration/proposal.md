# Proposal: l10n_ve_pos_igtf Odoo 17 → 19 Migration

## Intent

Migrate the Venezuelan POS IGTF module from Odoo 17 to Odoo 19 so it loads and calculates IGTF correctly in the new POS API. The module is currently unloadable due to renamed/moved imports and API changes in `point_of_sale`.

## Scope

### In Scope
- Update JS imports and class references to Odoo 19 (`PosOrder`, `PosPayment`, `pos_hook`).
- Add compat wrappers for renamed methods/getters in `order_model.js`.
- Migrate `update_igtf()` and `add_paymentline_without_igtf()` to Odoo 19 patterns.
- Update `payment_status.js` getters and `formatCurrency` calls.
- **Adapt `_create_payment_moves` in `pos_payment.py`** for Odoo 19 POS session payment move API (replaces `_credit_amounts`/`_debit_amounts`).
- Verify view XML IDs against Odoo 19 core `point_of_sale` views.
- Adjust `payment_status.xml` XPath selectors if O19 template structure changed.
- Verify module loads and IGTF behavior is preserved.

### Out of Scope
- New IGTF features or formula changes.
- Field deduplication — `l10n_ve_igtf` centralized backend fields but not POS-specific ones; `l10n_ve_pos_igtf` retains all its field definitions.
- Changes to `l10n_ve_pos` helpers (all required helpers are active on this branch).
- Other Python models (`pos_config.py`, `pos_payment_method.py`, `pos_session.py`, `pos_order.py`) — verified compatible, no changes needed.

## Capabilities

> This migration preserves existing business behavior while moving to the Odoo 19 POS API. There are no prior specs for this module.

### New Capabilities
- `l10n-ve-pos-igtf`: IGTF tax calculation in POS for Venezuela, migrated to Odoo 19.

### Modified Capabilities
- None.

## Approach

Use the compat-wrapper strategy: add thin wrappers for mechanical Odoo 17 → 19 API renames (e.g., `get_paymentlines()` → `this.payment_ids`), then rewrite the two complex methods (`update_igtf`, `add_paymentline_without_igtf`) using Odoo 19 model creation and l10n_ve_pos helpers (`localToForeign`, `set_foreign_amount`). This separates mechanical changes from logic migration and keeps the diff reviewable (~210 lines).

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `static/src/app/overrides/models/order_model.js` | Modified | Core IGTF logic, wrappers, O19 API migration |
| `static/src/app/overrides/models/payment_model.js` | Modified | Import fix, field definitions |
| `static/src/app/overrides/screens/payment_screen.js` | Modified | Trigger `update_igtf` via O19 API |
| `static/src/app/overrides/screens/payment_status.js` | Modified | Getters, `formatCurrency` calls |
| `static/src/app/overrides/screens/payment_status.xml` | Modified | XPath/template adjustments |
| `models/pos_payment.py` | Modified | `_create_payment_moves` adaptation for O19 payment move API |
| `views/pos_order.xml` | Verified | Check view IDs against O19 core |
| `views/pos_payment_method.xml` | Verified | Check view IDs against O19 core |
| `views/pos_payment_views.xml` | Verified | Check view IDs against O19 core |
| Other Python models | None | `pos_config.py`, `pos_payment_method.py`, `pos_session.py`, `pos_order.py` — verified compatible |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| `add_paymentline_without_igtf` manual payment creation breaks in O19 | High | Rewrite with `models["pos.payment"].create()` and test exact due/IGTF amounts |
| `?.() \|\| 0` silent-trap produces wrong values after method→getter changes | High | Replace every `?.()` with explicit getter access or `typeof` guard |
| `_create_payment_moves` uses deprecated O19 POS session helpers | High | Adapt to Odoo 19 payment move API; verify journal entries match O17 behavior |
| `update_igtf()` complex nested loops regress | Medium | Add functional tests covering multi-payment and foreign-currency scenarios |
| `payment.payment_method` → `payment.payment_method_id` skips IGTF branch | Medium | Global replacement and explicit null checks |
| XML view IDs may not match O19 core | Low | Verify against Odoo 19 `point_of_sale` view registry |

## Rollback Plan

Revert the commit on branch `19.0_mig-ta_73181_cashier_screen`. If post-deploy, checkout the previous commit and restart the Odoo service.

## Dependencies

- `l10n_ve_pos` (foreign currency POS helpers) — already migrated on this branch.
- `l10n_ve_igtf` (backend IGTF config) — unchanged.
- Odoo 19 core `point_of_sale` model APIs.

## Success Criteria

- [ ] Module installs and loads without JS errors in Odoo 19.
- [ ] IGTF amount calculates correctly for foreign payment methods.
- [ ] Foreign/local amount display matches O17 behavior.
- [ ] `_create_payment_moves` produces correct journal entries (IGTF split, foreign currency amounts).
- [ ] Existing POS flows (payment, change, refund) remain unaffected.
- [ ] Views render correctly with Odoo 19 `point_of_sale` core templates.

## Proposal Question Round

To refine assumptions before spec/design:

1. Should the IGTF percentage/rate rules remain exactly as in O17, or are there planned regulatory changes to apply during migration?
2. Are there specific POS payment workflows (split payments, refunds, exchanges) that must be regression-tested beyond the standard happy path?
3. Should we preserve the O17 UI text/copy in `payment_status.xml`, or update it to match any O19 core label changes?
