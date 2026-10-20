# Technical Design: l10n_ve_pos Odoo 17 → 19 Migration Plan

## 1) Objective

Define the implementation-ready technical blueprint for migrating `l10n_ve_pos` from Odoo 17 POS extension points to Odoo 19 patterns, while preserving Venezuelan foreign-currency behavior and keeping delivery in small, reviewable slices.

This design is planning-only. No runtime code changes are part of this change.

---

## 2) Architecture and Sequencing

### 2.1 Migration slices (dependency order)

1. **Slice A — Data Loading**
   - Replace session loader legacy APIs.
   - Output: all custom fields/domains/contexts available in Odoo 19 load payload.

2. **Slice B — Order/Payment Serialization**
   - Replace order/payment serialization hooks removed in Odoo 19.
   - Output: foreign fields available end-to-end in backend/frontend reads.

3. **Slice C — Session Accounting (High Risk)**
   - Adapt accumulators and accounting move creation to Odoo 19 structures.
   - Output: balanced accounting with preserved `foreign_amount` semantics.

4. **Slice D — Frontend Re-activation/Cleanup**
   - Re-enable required JS foreign-currency flows that are currently commented out.
   - Output: frontend sends/receives required foreign fields consistently.

5. **Slice E — Verification & Polish**
   - Cross-check remaining overrides, version bump, and migration closure checks.
   - Output: verified migration readiness and downstream unblock report.

### 2.2 Why this order

- Slices B and D consume data contracts produced in A.
- Slice C depends on values produced in A+B and can corrupt accounting if done early.
- Slice E validates all contracts after behavior is fully wired.

---

## 3) API Mapping Strategy (Odoo 17 → Odoo 19)

### 3.1 Data loading family

| Odoo 17 API | Odoo 19 Target | Module Area | Migration Rule |
|---|---|---|---|
| `load_pos_data()` | `load_data()` (+ extension keys) | `pos_session.py` | Rename entrypoint and preserve custom payload keys (e.g., `prefix_vats`) |
| `_loader_params_*` | `_load_pos_data_fields` / `_load_pos_data_domain` / `_load_pos_data_relations` | `pos_session.py` | Move field/domain/context concerns into model-specific Odoo 19 hooks |
| `_get_pos_ui_*` | `_load_pos_data_read` / `_load_pos_data_search_read` | `pos_session.py` | Replace custom UI-read methods with Odoo 19 read/search-read hooks |
| `_pos_ui_models_to_load` customizations | Odoo 19 model-loading hooks | `pos_session.py` | Preserve model load list and dependencies through native hook chain |

### 3.2 Serialization family

| Odoo 17 API | Odoo 19 Target | Module Area | Migration Rule |
|---|---|---|---|
| `_order_fields(ui_order)` | `_load_pos_data_fields` + `_load_pos_data_read` | `pos_order.py` | Stop injecting write payload through removed method; expose required fields via load contracts |
| `_payment_fields(order, ui_paymentline)` | `_load_pos_data_fields` on payment model | `pos_order.py` / `pos_payment.py` | Move field contract to payment model hooks |
| `_export_for_ui(...)` (order/payment/line) | `_load_pos_data_*` family | `pos_order.py`, `pos_payment.py`, `pos_order_line.py` | Remove export-time augmentation and rely on consistent load-read contracts |

### 3.3 Session accounting family

| Odoo 17 API | Odoo 19 Target | Risk | Migration Rule |
|---|---|---|---|
| `_accumulate_amounts(data)` | Odoo 19 accumulator shape | Critical | Build explicit key-map from legacy dict keys to Odoo 19 `amount`/`amount_converted` groups, preserving custom `foreign_amount` |
| `_update_amounts(...)` | Odoo 19 accumulator helpers | High | Ensure update path writes both native amount keys and custom foreign keys |
| `_create_split_account_payment(...)` | Odoo 19 return contract (`account.move.line` records) | Critical | Refactor call sites to follow new return type and set foreign fields on actual created records |
| `_create_bank_payment_moves(...)` | Odoo 19 payment/receivable line structures | High | Re-map receivable-line access and preserve `foreign_debit/foreign_credit` writes |
| `_create_cash_statement_lines_and_cash_move_lines(...)` | Odoo 19 cash statement + move-line outputs | High | Re-map response keys and keep foreign line annotation logic |
| `_create_invoice_receivable_lines(...)` | Odoo 19 invoice receivable structures | High | Align combined/split receivable structures and preserve foreign aggregation |

---

## 4) Data-Contract Invariants (Frontend ↔ Backend)

These invariants MUST hold after migration:

1. **Rate invariants**
   - `foreign_rate` and `foreign_inverse_rate` remain available where accounting/payment logic consumes them.
   - Rate direction must be explicit per contract (no heuristic-only interpretation).

2. **Foreign amount invariants**
   - `foreign_amount_total` is preserved on order-level accounting paths.
   - `foreign_amount` survives split/combine flows for cash/bank/invoice receivables.

3. **Line invariants**
   - Order lines preserve foreign value fields required for totals and tax calculations.

4. **Move line invariants**
   - Created accounting lines continue to receive `foreign_debit` / `foreign_credit` and `not_foreign_recalculate` where previously expected.

5. **Loader invariants**
   - Session payload still includes `prefix_vats`, `inverse_rate`, `is_foreign_currency`, and custom partner/product/company fields previously loaded.

---

## 5) Validation Strategy by Slice

### Slice A — Data Loading
- Verify POS session boot payload contains all migrated custom fields.
- Verify domain/context behavior for `res.currency` and limited product loading.

### Slice B — Serialization
- Verify order and payment creation flows include required foreign fields without `_order_fields/_payment_fields/_export_for_ui`.
- Verify frontend reads receive equivalent data through `_load_pos_data_*`.

### Slice C — Session Accounting
- Run multi-currency close-session scenarios (cash, bank, split, combined, invoiced, refund).
- Assert accounting move balance and expected foreign annotations.
- Compare before/after data-key map to detect dropped keys.

### Slice D — Frontend
- Re-enable and validate commented model overrides only if still needed in Odoo 19 flow.
- Verify foreign amounts from UI reach backend and return to display consistently.

### Slice E — Verification & Polish
- End-to-end smoke run for VES/USD order lifecycle.
- Verify no remaining legacy API symbol in migrated paths.
- Confirm downstream blocker status table is updated.

---

## 6) Rollback Boundaries and Risk Controls

### 6.1 Rollback boundaries
- One rollback boundary per slice (A–E).
- If a slice fails validation, revert only that slice, keep prior validated slices.

### 6.2 Risk controls
- **Critical controls** for Slice C:
  - Mandatory data-key map review before implementation merge.
  - Mandatory accounting validation scenarios before advancing.
- **Contract controls** for A/B/D:
  - Field-presence checklist and payload snapshot checks.
- **Scope controls**:
  - No incidental refactors outside mapped migration symbols.

---

## 7) Commit and Reviewability Plan

- Target **≤400 changed lines per implementation slice**.
- If forecast exceeds budget:
  - Split slice into sub-slices by method family (especially in session accounting).
- Preferred work-unit pattern per slice:
  1. API mapping + minimal adaptation
  2. Contract validation
  3. Stabilization cleanup (only if required)

---

## 8) Deliverables Hand-off to Tasks Phase

`tasks.md` must include:
- Concrete tasks for slices A–E
- File-level touch map per task
- Forecast line-count per task and split flags
- Validation checkpoints per task
- Downstream unblock milestones (`l10n_ve_pos_igtf`, `l10n_ve_pos_mf`, `integra-addons`)
