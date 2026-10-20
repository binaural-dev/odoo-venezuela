# Exploration: l10n_ve_pos Migration — Odoo 17 → 19

## Odoo 19.0 Reference

**Path used**: `/home/binaural19/odoo` → `addons/point_of_sale/` (version `19.0 final`)

---

## Current State

`l10n_ve_pos` (version `1.2`) is a Venezuelan POS localization module extending `point_of_sale`. It adds foreign currency (VES/USD) handling, dual-currency pricing, tax adaptation, and multi-currency session closing with foreign amount tracking across accounting entries. It has **~55 source files** (excluding `__pycache__`). The current codebase still uses **Odoo 17-era APIs** and has **not been migrated to Odoo 19**. Several JS patches are already partially migrated (correct Odoo 19 import paths), while others are fully commented out.

The module is a **blocking dependency** for `l10n_ve_pos_igtf`, `l10n_ve_pos_mf`, and **14 `integra-addons` modules** that are already stamped `19.0.1.0.0`.

---

## Migration Gaps — Top 5 Critical

| # | Gap | Files | Odoo 17 → 19 | Risk |
|---|-----|-------|-------------|------|
| 1 | **`_order_fields()` / `_payment_fields()` removed** | `models/pos_order.py` | Replaced by `_load_pos_data_fields` + `_load_pos_data_read` on `pos.order` and `pos.payment` | **BLOCKING** — order creation fails |
| 2 | **`_export_for_ui()` × 3 removed** | `models/pos_order.py:41`, `pos_payment.py:25`, `pos_order_line.py:66` | Replaced by `_load_pos_data_*` framework | **BLOCKING** — UI data serialization broken |
| 3 | **`load_pos_data()` → `load_data()` + 8× `_loader_params_*` → new system** | `models/pos_session.py:20-85` | `load_data()`, `load_data_params()`, `_load_pos_data_fields()`, `_load_pos_data_domain()`, `_load_pos_data_relations()` | **BLOCKING** — session data loading broken |
| 4 | **`_accumulate_amounts()` data structure changed** | `models/pos_session.py:579-658` | Now uses `amount`/`amount_converted` dicts. Custom `foreign_amount` injection must adapt to new dict structure; 5 new accumulator groups (`sales`, `taxes`, `stock_expense`, etc.) | **HIGH** — accounting entries miscomputed |
| 5 | **`_create_split_account_payment()` return type changed** | `models/pos_session.py:451-475` | Odoo 19 returns `account.move.line` record set, not move object. Access chain `res.move_id.payment_id` is broken | **BLOCKING** — split payment accounting fails |

---

## Full Gap Inventory

### Python Models — Breaking API Changes

**`models/pos_order.py`:**
| Method | Odoo 17 | Odoo 19 Action | Status |
|--------|---------|----------------|--------|
| `_order_fields(ui_order)` | Line 16 — adds `foreign_amount_total`, `foreign_currency_rate` | Migrate to `_load_pos_data_fields` + `_load_pos_data_read` on `pos.order` | ❌ Must rewrite |
| `_payment_fields(order, ui_paymentline)` | Line 23 — adds `foreign_amount`, `foreign_rate` | Migrate to `_load_pos_data_fields` on `pos.payment` | ❌ Must rewrite |
| `_export_for_ui(order)` | Line 41 — adds `foreign_currency_rate` | Removed — use `_load_pos_data_*` | ❌ Must rewrite |
| `_export_for_ui(orderline)` | Line 66 (PosOrderLine) — adds `foreign_price`, `foreign_currency_rate` | Removed | ❌ Must rewrite |
| `_prepare_invoice_vals()` | Line 29 — adds `foreign_rate`, `foreign_inverse_rate`, `manually_set_rate` | Needs review — verify invoice creation flow | ⚠️ Verify |
| `_get_invoice_lines_values()` | Line 50 — adds `foreign_price` | Needs review | ⚠️ Verify |
| `_prepare_refund_data()` | Line 61 (PosOrderLine) — adds `foreign_price` | Needs review | ⚠️ Verify |

**`models/pos_session.py`:**
| Method | Odoo 17 | Odoo 19 Action | Status |
|--------|---------|----------------|--------|
| `load_pos_data()` | Line 20 — calls `super().load_pos_data()`, adds `prefix_vats` | Renamed to `load_data()` in base. Must call `super().load_data()` | ❌ Must rename |
| `delete_opening_control_session()` | Line 25 — stub returning `{"status": "success"}` | Odoo 19 has real impl. This stub prevents session cancellation | ⚠️ Review / Remove stub |
| `_loader_params_pos_payment()` | Line 33 | → `_load_pos_data_fields` on `pos.payment` | ❌ Must rewrite |
| `_loader_params_pos_payment_method()` | Line 38 | → `_load_pos_data_fields` on `pos.payment.method` | ❌ Must rewrite |
| `_loader_params_account_tax()` | Line 43 | → `_load_pos_data_fields` on `account.tax` | ❌ Must rewrite |
| `_loader_params_res_partner()` | Line 48 | → `_load_pos_data_fields` on `res.partner` | ❌ Must rewrite |
| `_loader_params_res_currency()` | Line 54 | → `_load_pos_data_fields` on `res.currency` | ❌ Must rewrite |
| `_loader_params_product_product()` | Line 65 | → `_load_pos_data_fields` on `product.product` | ❌ Must rewrite |
| `_loader_params_res_company()` | Line 75 | → `_load_pos_data_fields` on `res.company` | ❌ Must rewrite |
| `_get_pos_ui_res_currency()` | Line 137 | Migrate to `_load_pos_data_read()` | ❌ Must rewrite |
| `_get_pos_ui_product_category()` | Line 311 | Migrate to `_load_pos_data_read()` | ❌ Must rewrite |
| `_process_pos_ui_product_product()` | Line 323 | Migrate to `_load_pos_data_read()` | ❌ Must rewrite |
| `action_pos_session_close()` | Line 375 — signature matches Odoo 19 ✓ | Calls super, then does rounding + empty `_adjust_accounting_entries` | ⚠️ Verify compatibility |
| `_accumulate_amounts(data)` | Line 579 — massive override adding `foreign_amount` to ALL dicts | Odoo 19 uses `amount`/`amount_converted` only. Must adapt | 🔴 HIGH |
| `_update_amounts()` | Line 660 — adds `foreign_amount` to amounts dict | Odoo 19 only has `amount`/`amount_converted` | 🔴 HIGH |
| `_create_account_move()` | Line 557 — signature OK, writes `foreign_rate` on `self.move_id` | Already matches ✓ | ⚠️ Verify |
| `_create_bank_payment_moves()` | Line 698 — sets `foreign_debit/credit` on receivable lines | Odoo 19 dict structure changed. Must verify `payment_to_receivable_lines` keys | 🔴 HIGH |
| `_create_split_account_payment()` | Line 451 — tries `res.move_id.payment_id` | Odoo 19 returns `account.move.line` record set. Access chain BROKEN | ❌ BLOCKING |
| `_create_cash_statement_lines_and_cash_move_lines()` | Line 725 — reads from `res` dict, calls `set_foreign_amount_in_line()` | Odoo 19 returns different dict structure | 🔴 HIGH |
| `_create_invoice_receivable_lines()` | Line 672 — accesses `res["combine_invoice_receivable_lines"]` | Odoo 19 uses `combine_inv_payment_receivable_lines` record sets | 🔴 HIGH |
| `set_foreign_amount_in_line()` | Line 745 — helper for cash line foreign amounts | Uses `float_compare` to detect matching lines | ⚠️ Verify |
| Cross-move code | Lines 156-310, 349-373, 477-555 | All **already commented out** | ✅ No action |

**`models/pos_payment.py`:**
| Method | Odoo 17 | Odoo 19 Action | Status |
|--------|---------|----------------|--------|
| `_export_for_ui(payment)` | Line 25 — adds `foreign_rate`, `foreign_amount` | Removed | ❌ Must rewrite |
| `_create_payment_moves(is_reverse)` | Line 31 — writes `foreign_rate`, `foreign_inverse_rate` on matching move | Signature matches ✓. Needs verification of `filtered(lambda: ...)` float comparison | ⚠️ Verify |

**`models/pos_config.py`** — needs checking for POS IoT references.

### JavaScript — Already Partially Migrated

| File | Odoo 19 Import Paths | Status |
|------|---------------------|--------|
| `pos_order.js` | `@point_of_sale/app/models/pos_order` ✅ | Large commented-out blocks (300+ lines). Active code OK |
| `pos_order_line.js` | `@point_of_sale/app/models/pos_order_line` ✅ | Active code uses `accountTaxHelpers` from `@account/helpers/account_tax` — verify |
| `product_model.js` | Entirely **commented out** | ⚠️ Dead code — no price-in-foreign-currency override active |
| `pos_model.js` | Entirely **commented out** | ⚠️ Dead code — no `_processData` override active |
| `payment_model.js` | Entirely **commented out** | ⚠️ Dead code — no `export_as_JSON` override for foreign amounts |
| `payment_screen.js` | `@point_of_sale/app/screens/payment_screen/payment_screen` ✅ | Active code OK |
| `product_screen.js` | `@point_of_sale/app/screens/product_screen/product_screen` ✅ | Active code OK |
| `product_card.js` | `@point_of_sale/app/components/product_card/product_card` ✅ | Active code OK |
| `contextual_utils_service.js` | `@point_of_sale/app/services/contextual_utils_service` ✅ | Active code OK |
| `payment_status.js` | `@point_of_sale/app/screens/payment_screen/payment_status/payment_status` ✅ | Active code OK |
| `payment_line.js` | `@point_of_sale/app/screens/payment_screen/payment_lines/payment_lines` ✅ | Active code OK |
| `orderline.js` | Component-level, active | ✓ |
| `ticket_screen.js` | Imports `FullRefundButton` from local module | ⚠️ Cross-module import needs verification |
| `partner_editor.js` | Not reviewed | — |
| `partner_list.js` | Not reviewed | — |
| `order_display.js` | Not reviewed | — |
| `closing_popup.xml` | Not reviewed | — |

### XML Templates
All templates use `t-*` OWL syntax with `owl="1"` — **compatible** with Odoo 19. No breaking changes expected.

### Manifest
- Assets bundle: `"point_of_sale._assets_pos"` — correct for Odoo 19 ✓
- Dependencies: No `pos_iot` (correct for base module) ✓
- Version: `"1.2"` — should bump to `19.0.1.0.0` after migration

---

## Evaluation: `POS_MIGRATION_ESTIMATES.md`

**Verdict: Partially useful — needs significant adjustment.**

### What works:
- **Functional categorization** (Órdenes, Pagos, Cierre de caja, etc.) is a reasonable grouping for organizing work
- High-level descriptions are clear for stakeholder communication
- The modular separation (l10n_ve_pos → igtf → mf) is correct

### What needs adjustment:
| Issue | Detail |
|-------|--------|
| **Hours overestimated** | 48h vs 35h (plan doc at no-assist) and 16.5h (with assist) — ~37% over |
| **No technical mapping** | Lists "Órdenes de venta 5.5h" but doesn't map to `_order_fields`, `_export_for_ui`, etc. |
| **Python/JS mixed** | Each functional area blends backend and frontend work — can't estimate separately |
| **No gap analysis** | Doesn't identify _why_ things break (API changes, import paths, etc.) |
| **Embedded images** | Decorative base64 PNG headers make the file hard to maintain in version control |
| **No data on what's already migrated** | Doesn't account for JS files that already have correct Odoo 19 imports |

### Recommendation:
Use the functional categories from estimates as **task group labels**, but derive the actual scope from the gap analysis in this exploration. The estimate hours from `POS_MIGRATION_PLAN.md` (the table with per-method breakdown) are more actionable.

---

## Proposed Migration Slices

Designed for **small commits, low review burden** (under 400 lines each):

### Slice 1: Data Loading Overhaul
- **Focus**: Replace `load_pos_data()` → `load_data()` + 8× `_loader_params_*` → `_load_pos_data_*`
- **Files**: `models/pos_session.py` (lines 20-85)
- **Also**: Remove `delete_opening_control_session` stub or fix it
- **Est. size**: ~150 lines changed
- **Risks**: None if following Odoo 19 pattern exactly

### Slice 2: Order & Payment Serialization
- **Focus**: Replace `_order_fields`, `_payment_fields`, `_export_for_ui` × 3 with `_load_pos_data_fields`/`_load_pos_data_read`
- **Files**: `models/pos_order.py`, `models/pos_payment.py`, `models/pos_session.py` (UI methods)
- **Est. size**: ~200 lines changed
- **Risks**: Must test end-to-end order creation

### Slice 3: Session Closing — Accounting (HIGH RISK)
- **Focus**: Fix `_accumulate_amounts`, `_create_split_account_payment`, `_create_bank_payment_moves`, `_create_cash_statement_lines_and_cash_move_lines`, `_create_invoice_receivable_lines`
- **Files**: `models/pos_session.py` (lines 451-743), `models/pos_payment.py`
- **Est. size**: ~350 lines changed
- **Risks**: HIGH — accounting data structures differ. Must test with multi-currency orders

### Slice 4: JS Cleanup & Activation
- **Focus**: Un-comment / re-implement `payment_model.js`, `pos_model.js`, `product_model.js`; clean up dead commented code in `pos_order.js`
- **Files**: 3 JS files + `pos_order.js`
- **Est. size**: ~150 lines changed
- **Risks**: Low — mostly enabling existing patterns

### Slice 5: Remaining Verification & Polish
- **Focus**: Verify all remaining overrides (`_prepare_invoice_vals`, `_get_invoice_lines_values`, `_prepare_refund_data`, `_create_payment_moves`); manifest version bump; XML template review
- **Files**: Multiple small touches
- **Est. size**: ~100 lines
- **Risks**: Low

---

## Affected Areas — Full File Map

### Python Models
- `models/pos_order.py` — 4 breaking changes, 3 verify
- `models/pos_session.py` — 12 breaking changes, 2 high risk, ~8 sub-methods
- `models/pos_payment.py` — 1 breaking, 1 verify
- `models/pos_config.py` — verify (IoT references)
- `models/pos_order_line.py` — 1 verify (indirect, no override to migrate)

### JavaScript
- `static/src/overrides/models/pos_order.js` — cleanup dead code
- `static/src/overrides/models/payment_model.js` — re-activate
- `static/src/overrides/models/pos_model.js` — re-activate
- `static/src/overrides/models/product_model.js` — re-activate
- `static/src/overrides/components/orderline/orderline.js` — verify

### Configuration
- `__manifest__.py` — version bump

---

## Risks

| Risk | Level | Mitigation |
|------|-------|------------|
| `_accumulate_amounts` data structure mismatch causes accounting errors in live sessions | 🔴 Critical | Test with real multi-currency orders; compare generated account moves |
| `_create_split_account_payment` return type change silently breaks bank payment moves | 🔴 Critical | Trace call chain; add type assertion in migration |
| Commented-out JS patches (`payment_model.js`, `pos_model.js`) mean foreign amounts may not flow from UI to backend | 🟠 High | Re-enable and test end-to-end order with foreign currency |
| `delete_opening_control_session` stub prevents session cancellation | 🟡 Medium | Review and either delegate to super or remove |
| Large commented-out code blocks cause confusion about intent | 🟢 Low | Clean up in Slice 4 |
| 15 integra-addons modules depend on l10n_ve_pos — migration delay blocks them | 🟡 Medium | Prioritize Slice 1+2 for basic API compatibility |

---

## Ready for Proposal

**Yes.** The analysis is complete enough to design the migration. Suggested next phases:

1. **sdd-propose**: Formalize the migration approach, tooling, testing strategy, and rollback plan
2. **sdd-design**: Detail the `_load_pos_data_*` mapping for each model and the accounting data structure adaptation
3. **sdd-tasks**: Break into the 5 slices above and forecast review budget

The execution order should follow the slices: **Data Loading → Serialization → Accounting → JS → Polish**.
