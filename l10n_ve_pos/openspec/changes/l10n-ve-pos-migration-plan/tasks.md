# Tasks: l10n_ve_pos Odoo 17 → 19 Migration Plan

> Planning-blueprint hand-off. Each slice (A-E) becomes one implementation change executed via `sdd-apply`. This change itself is planning-only; the tasks below describe the runtime migration work that follow-up changes will perform.

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~980 total across 5 slices (6 PRs with C split) |
| 400-line budget risk | High (overall); per-slice Low/Medium |
| Chained PRs recommended | Yes |
| Suggested split | PR1 Slice A → PR2 Slice B → PR3 Slice C1 → PR4 Slice C2 → PR5 Slice D → PR6 Slice E |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending (user must choose: stacked-to-main vs feature-branch-chain) |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High

### Mandatory Justification Gate (Reviewer-in-the-loop)

- Every implementation PR MUST include a short **"Why this change"** note per touched method family.
- That note MUST reference **Odoo native evidence** (commit URL, PR URL, or exact core file/line in 19.0) that justifies the migration decision.
- No slice is considered done without:
  1) maintainer verification checkpoint completed,
  2) native Odoo evidence attached,
  3) rollback note confirmed.

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| A | Data loading migration | PR 1 | base = main/tracker; ~150 lines; unblocks B, D |
| B | Order/payment serialization | PR 2 | base = PR 1; ~200 lines; unblocks D, downstream |
| C1 | Accounting accumulators | PR 3 | base = PR 2; ~180 lines; high risk |
| C2 | Accounting move creation | PR 4 | base = PR 3; ~200 lines; high risk |
| D | Frontend re-activation | PR 5 | base = PR 4; ~150 lines |
| E | Verification & polish | PR 6 | base = PR 5; ~100 lines; closes migration |

### Downstream Unblocking Map

| Milestone | Unblocks | Priority |
|-----------|----------|----------|
| Slice A + B done | `l10n_ve_pos_igtf`, `l10n_ve_pos_mf` basic API compat | High |
| Slice C done | Downstream session-closing accounting extensions | High |
| Slice D done | Downstream frontend foreign-currency flows | Medium |
| Slice E done | 14 `integra-addons` modules (version stamp 19.0.1.0.0 alignment, full closure) | Medium |

---

## Slice A — Data Loading (Phase 1)

**Files**: `models/pos_session.py` (lines 20-85, 137, 311, 323) | **Forecast**: ~150 lines | **Budget**: within | **Rollback**: revert this slice only; no downstream consumer yet.

- [x] A.1 Rename `load_pos_data()` → `load_data()` in `pos_session.py:20`; keep payload aligned to Odoo 19 loader contract (model keys only, no ad-hoc top-level `prefix_vats`). (~20 lines)
- [x] A.2 Migrate 7× `_loader_params_*` → `_load_pos_data_fields` for `pos.payment` (`foreign_rate`), `pos.payment.method` (`is_foreign_currency`), `account.tax` (`type_tax_use`), `res.partner` (`prefix_vat`, `city_id`), `res.currency` (`inverse_rate`), `product.product` (`free_qty`, `qty_available`, warehouse context), `res.company`. `pos_session.py:33-85`. (~80 lines)
- [x] A.3 Migrate `_get_pos_ui_res_currency` (`:137`), `_get_pos_ui_product_category` (`:311`), `_process_pos_ui_product_product` (`:323`) → `_load_pos_data_read` / `_load_pos_data_search_read`; preserve `res.currency` domain filter. (~40 lines)
- [x] A.4 Resolve `delete_opening_control_session` stub (`:25`): delegate to super or remove. (~10 lines)
- [x] A.5 **Verify**: open POS session → frontend payload keeps model-key structure (no ad-hoc top-level `prefix_vats`) and exposes `foreign_rate`, `is_foreign_currency`, `inverse_rate`, `qty_available`; limited-products config still loads `free_qty` + warehouse context. Spec: `pos-odoo19-data-loading`.
- [x] A.6 **Evidence**: attach Odoo 19 native reference proving `load_data` + `_load_pos_data_*` usage for equivalent models.

---

## Slice B — Order/Payment Serialization (Phase 2)

**Depends on**: A | **Files**: `models/pos_order.py`, `models/pos_payment.py`, `models/pos_order_line.py` | **Forecast**: ~200 lines | **Budget**: within | **Rollback**: revert; A remains valid independently.

- [ ] B.1 Migrate `_order_fields(ui_order)` (`pos_order.py:16`) → `_load_pos_data_fields` + `_load_pos_data_read` on `pos.order`; preserve `foreign_amount_total`, `foreign_currency_rate`. (~40 lines)
- [ ] B.2 Migrate `_payment_fields(order, ui_paymentline)` (`pos_order.py:23`) → `_load_pos_data_fields` on `pos.payment`; preserve `foreign_amount`, `foreign_rate`. (~30 lines)
- [ ] B.3 Migrate `_export_for_ui(order)` (`pos_order.py:41`) → `_load_pos_data_*` on `pos.order`. (~30 lines)
- [ ] B.4 Migrate `_export_for_ui(payment)` (`pos_payment.py:25`) → `_load_pos_data_*` on `pos.payment`. (~30 lines)
- [ ] B.5 Migrate `_export_for_ui(orderline)` (`pos_order_line.py:66`) → `_load_pos_data_*` on `pos.order.line`; preserve `foreign_price`, `foreign_currency_rate`; ensure refund copies `foreign_price`. (~30 lines)
- [ ] B.6 **Verify**: multi-currency order create → reload round-trip retains all foreign fields; refund preserves `foreign_price`. Spec: `pos-odoo19-serialization`.
- [ ] B.7 **Evidence**: attach Odoo 19 native reference showing order/payment/line read contracts replacing `_order_fields`/`_payment_fields`/`_export_for_ui`.

---

## Slice C — Session Accounting (Phase 3, HIGH RISK)

**Depends on**: A, B | **Files**: `models/pos_session.py` (lines 451-743), `models/pos_payment.py:31` | **Total forecast**: ~380 lines | **Budget**: SPLIT required (design §7 — split by method family) → C1 + C2.

### Slice C1 — Accumulators (PR 3)

**Forecast**: ~180 lines | **Rollback**: revert C1; A+B remain valid; C2 not yet started.

- [x] C1.1 Build before/after data-key map for `_accumulate_amounts` (Odoo 17 keys → Odoo 19 `amount`/`amount_converted` + custom `foreign_*`). Doc artifact in change folder. (~40 lines)
- [x] C1.2 Adapt `_accumulate_amounts` (`pos_session.py:579-658`) to Odoo 19 dict shape; preserve `foreign_amount` aggregation for split/combine cash, bank, invoice receivables. (~100 lines)
- [x] C1.3 Adapt `_update_amounts` (`pos_session.py:660`) to write both native amount keys and custom foreign keys. (~30 lines)
- [x] C1.4 **Verify**: split cash + invoiced bank → accumulated dict has `amount`/`amount_converted` AND `foreign_amount`; multi-currency session close balances. Spec: `pos-odoo19-session-accounting`.
- [x] C1.5 **Evidence**: attach Odoo 19 native reference for accumulator key structure consumed by closing methods.

### Slice C2 — Move Creation (PR 4)

**Depends on**: C1 | **Forecast**: ~200 lines | **Rollback**: revert C2; C1 accumulators remain valid.

- [x] C2.1 Fix `_create_split_account_payment` (`pos_session.py:298-346`): Odoo 19 returns `account.move.line` recordset, not move object; refactor `res.move_id.payment_id` access chain to `receivable_lines.move_id.origin_payment_id`; set `foreign_rate`/`foreign_inverse_rate` on created records; short-circuit safely on empty (no-journal) recordset. (~50 lines)
- [ ] C2.2 Adapt `_create_bank_payment_moves` (`pos_session.py:698`): re-map `payment_to_receivable_lines` keys; preserve `foreign_debit`/`foreign_credit` writes. (~50 lines)
- [ ] C2.3 Adapt `_create_cash_statement_lines_and_cash_move_lines` (`pos_session.py:725`): re-map response dict; keep `set_foreign_amount_in_line` helper (`:745`). (~40 lines)
- [ ] C2.4 Adapt `_create_invoice_receivable_lines` (`pos_session.py:672`): align to `combine_inv_payment_receivable_lines` record sets; preserve foreign aggregation. (~40 lines)
- [ ] C2.5 Verify `_create_payment_moves` (`pos_payment.py:31`): foreign-field writes on matching move; float-compare filter still valid. (~20 lines)
- [ ] C2.6 **Verify**: multi-currency close (cash, bank, split, combined, invoiced, refund) → session move balances; foreign annotations present on all created lines; no unreconciled foreign difference on refund. Spec: `pos-odoo19-session-accounting`.
- [ ] C2.7 **Evidence**: attach Odoo 19 native reference for return contracts/recordsets in split/bank/cash/invoice move creation paths.

**Split justification**: Accumulators (C1) produce the data dict consumed by move creation (C2). Separating them yields two reviewable units ≤200 lines each, isolates the highest-risk accounting changes, and allows independent rollback of move-creation fixes without re-touching accumulator logic.

---

## Slice D — Frontend Re-activation (Phase 4)

**Depends on**: B (fields); benefits from C (accounting closure) | **Files**: `static/src/overrides/models/*.js`, `static/src/overrides/components/` | **Forecast**: ~150 lines | **Budget**: within | **Rollback**: revert; commented-out state returns; backend unchanged.

- [ ] D.1 Re-activate `payment_model.js`: `export_as_JSON` override for `foreign_amount`/`foreign_rate`. (~40 lines)
- [ ] D.2 Re-activate `pos_model.js`: `_processData` override for foreign-currency initial load. (~40 lines)
- [ ] D.3 Re-activate `product_model.js`: price-in-foreign-currency override. (~30 lines)
- [ ] D.4 Clean dead commented-out blocks in `pos_order.js`. (~30 lines)
- [ ] D.5 Verify `ticket_screen.js` cross-module `FullRefundButton` import resolves under Odoo 19. (~10 lines)
- [ ] D.6 **Verify**: payment screen shows foreign + local amount; ticket screen shows foreign totals/tax; refund preserves foreign values in UI; receipt renders VES/USD. Spec: `pos-odoo19-frontend`.
- [ ] D.7 **Evidence**: attach Odoo 19 frontend native reference for equivalent model/screen extension points used.

---

## Slice E — Verification & Polish (Phase 5)

**Depends on**: A-D | **Files**: `models/pos_order.py`, `models/pos_order_line.py`, `models/pos_config.py`, `__manifest__.py`, templates | **Forecast**: ~100 lines | **Budget**: within | **Rollback**: revert polish; migration behavior from A-D intact.

- [ ] E.1 Verify `_prepare_invoice_vals` (`pos_order.py:29`): `foreign_rate`, `foreign_inverse_rate`, `manually_set_rate` still written. (~15 lines)
- [ ] E.2 Verify `_get_invoice_lines_values` (`pos_order.py:50`): `foreign_price` preserved. (~15 lines)
- [ ] E.3 Verify `_prepare_refund_data` (`pos_order_line.py:61`): `foreign_price` copied to refund line. (~15 lines)
- [ ] E.4 Check `pos_config.py` for IoT references; remove if present. (~10 lines)
- [ ] E.5 Bump manifest version `1.2` → `19.0.1.0.0` in `__manifest__.py`. (~5 lines)
- [ ] E.6 Confirm XML templates remain OWL-compatible (no structural change needed). (~10 lines)
- [ ] E.7 **Verify**: end-to-end VES/USD order lifecycle smoke run; grep migrated paths for legacy symbols (`load_pos_data`, `_order_fields`, `_export_for_ui`, `_loader_params_`) → zero hits; update downstream blocker status table. Spec: `pos-odoo19-migration-planning`.
- [ ] E.8 **Evidence**: include final mapping appendix with all native Odoo references used across slices (URLs or file+line snapshots).

---

## Implementation Order & Dependencies

```
A (data loading) ──┬──► B (serialization) ──┬──► C1 (accumulators) ──► C2 (move creation) ──► D (frontend) ──► E (polish)
                   │                        │
                   └────────────────────────┴──► D (frontend also reads A contracts)
```

- A blocks all (produces data contracts).
- B consumes A; blocks D and C (C needs serialized foreign amounts).
- C1 blocks C2 (accumulator dict feeds move creation).
- D consumes A+B; runs after C for full closure validation.
- E validates all; closes migration and downstream unblock.
