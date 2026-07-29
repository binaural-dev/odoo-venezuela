# Apply Progress: l10n_ve_pos_igtf Odoo 17→19 Migration

## Overview
- **Change**: `l10n-ve-pos-igtf-migration`
- **Mode**: openspec
- **Date**: 2026-07-08

## Tasks Status

- [x] **T1**: Fix imports and patch targets (3 files: order_model.js, payment_model.js, payment_status.js)
- [x] **T2**: Add 6 compat wrappers + 2 existing IGTF overrides to PosOrder
- [x] **T3**: Mechanical renames (`payment_method`→`payment_method_id`, `cid`→`uuid`, `get_order()`→`currentOrder`)
- [x] **T4**: Fix formatCurrency calls (removed `'Product Price'` 2nd arg from 5 calls)
- [x] **T5**: Apply defensive getter patterns (use `payment_ids`/`totalDue` directly)
- [x] **T6**: Rewrite `add_paymentline_without_igtf` (use `models["pos.payment"].create`)
- [x] **T7**: Verify `_create_payment_moves` (add `from_pos=True` to context)
- [x] **T8**: Verify XML views (fix `payment_status.xml` XPath for O19, confirm other views)

## Files Changed
1. `static/src/app/overrides/models/order_model.js` — imports, wrappers, renames, T6 rewrite
2. `static/src/app/overrides/models/payment_model.js` — imports, patch target
3. `static/src/app/overrides/screens/payment_screen.js` — `pos.get_order()` → `currentOrder`
4. `static/src/app/overrides/screens/payment_status.js` — imports, renames, formatCurrency fix, defensive getters
5. `models/pos_payment.py` — `from_pos=True` context addition
6. `static/src/app/overrides/screens/payment_status.xml` — XPath selectors updated for O19

## Notes
- `payment_status.js` still has `get_rounding_applied()` calls (pre-existing, not in scope)
- `order_model.js` `get_max_total_with_igtf()` has `this.props.order` usage (pre-existing bug)
- All view XML parent IDs verified against Odoo 19 core
