# Apply Progress — l10n_ve_pos Odoo 17 → 19 Migration

**Change**: l10n-ve-pos-migration-plan
**Mode**: Strict TDD
**Module**: `l10n_ve_pos` (Odoo 19.0)
**Status**: Slice A + Slice B complete (A.1 → A.6, B.1 → B.7) — ⏸️ Pending maintainer review before Slice C
**Last run**: 2026-07-06
**Container**: `proj`
**Run command**: `docker exec -u odoo proj odoo -i l10n_ve_pos --without-demo=True --test-tags l10n_ve_pos --stop-after-init -d l10n_ve_pos_slice_b_final_<ts> -w odoo --db_port 5432`

---

## Cumulative Completed Checklist

### Slice A — Data Loading (✅ done 2026-07-04)

- [x] **A.1** — Renamed `load_pos_data()` → `load_data()` and removed ad-hoc top-level `prefix_vats` key. (`l10n_ve_pos/models/pos_session.py`)
- [x] **A.2** — Migrated 7× `_loader_params_*` to per-model `_load_pos_data_fields` overrides for `pos.payment`, `pos.payment.method`, `account.tax`, `res.partner`, `res.currency`, `product.product`, `res.company`.
- [x] **A.3** — Migrated `_get_pos_ui_res_currency`, `_get_pos_ui_product_category`, `_process_pos_ui_product_product` to `_load_pos_data_read` / `_load_pos_data_search_read`.
- [x] **A.4** — Preserved the `delete_opening_control_session` safe stub.
- [x] **A.5** — `tests/test_pos_data_loading.py` (11 unit tests, all green).
- [x] **A.6** — Native Odoo 19 evidence captured in §"Odoo 19 native evidence".

### Slice B — Order/Payment Serialization (✅ done 2026-07-06)

- [x] **B.1** — Migrated `pos.order._order_fields(ui_order)` → `pos.order._load_pos_data_fields` (adds `foreign_amount_total`, `foreign_currency_rate`); removed the dead `_order_fields` super-call override. (`l10n_ve_pos/models/pos_order.py`)
- [x] **B.2** — Verified `pos.payment._load_pos_data_fields` (set up in Slice A) keeps `foreign_amount`, `foreign_rate`, `foreign_currency_id` and the Odoo 19 core contract. (`l10n_ve_pos/models/pos_payment.py`)
- [x] **B.3** — Migrated `pos.order._export_for_ui(order)` → covered by B.1's `_load_pos_data_fields`; deleted the dead `_export_for_ui` override.
- [x] **B.4** — Migrated `pos.payment._export_for_ui(payment)` → covered by B.2's `_load_pos_data_fields`; deleted the dead `_export_for_ui` override.
- [x] **B.5** — Migrated `pos.order.line._export_for_ui(orderline)` → `pos.order.line._load_pos_data_fields` (now lists `foreign_price`, `foreign_subtotal`, `foreign_total`, **`foreign_currency_rate`**). Consolidated the duplicate `PosOrderLine` class: the `_prepare_refund_data` override now lives in `pos_order_line.py` (its natural home) and the related `foreign_currency_rate` field is declared there once.
- [x] **B.6** — End-to-end test (`tests/test_pos_serialization.py::test_pos_order_serialization_round_trip_preserves_foreign_fields`) creates a multi-currency order with two lines and one payment, exercises the Odoo 19 `pos.order.read_pos_data` path, asserts every foreign field round-trips. Companion test for the refund path (`test_pos_order_refund_copies_foreign_price_to_refund_line`) confirms the refund line keeps `foreign_price`.
- [x] **B.7** — Defensive test `test_legacy_serialization_hooks_are_removed` fails fast if any of `_order_fields`, `_payment_fields`, `_export_for_ui` is reintroduced. Native Odoo evidence captured in §"Odoo 19 native evidence".

---

## Odoo 19 native evidence (Slice B decisions)

| Decision | Native Odoo 19 reference | Note |
|----------|--------------------------|------|
| `pos.order._order_fields` is **removed** in Odoo 19 | `2a5f1abf2e98 [IMP] pos_*: refactoring with related models part 2` (`/home/binaural19/odoo/addons/point_of_sale/models/pos_order.py` history) — the Odoo 19 file (HEAD `cfd014b9d280`) has **no** `def _order_fields` symbol. (`grep -n "def _order_fields" /home/binaural19/odoo/addons/point_of_sale/models/pos_order.py` returns nothing.) | The legacy override `l10n_ve_pos/models/pos_order.py:_order_fields` was a dead method that would have raised `AttributeError: 'super' object has no attribute '_order_fields'` on the next call. Per the user's fail-fast rule, we deleted it instead of leaving it as silent debt. |
| `pos.order._payment_fields` is **removed** in Odoo 19 | Same commit `2a5f1abf2e98`. (`grep` returns nothing for `_payment_fields` in Odoo 19 `pos_order.py`.) | The legacy `l10n_ve_pos` override called `super()._payment_fields(...)` — would have raised the same `AttributeError`. Deleted. |
| `pos.order._export_for_ui` is **removed** in Odoo 19 | Same commit. (`grep -rn "def _export_for_ui" /home/binaural19/odoo/` returns only downstream l10n modules that still target 17.0.) | The legacy `l10n_ve_pos` overrides for order / orderline / payment called `super()._export_for_ui(...)` — would have raised. Deleted. |
| `pos.order._load_pos_data_fields` is the Odoo 19 read contract | `/home/binaural19/odoo/addons/point_of_sale/models/pos_load_mixin.py:70-72` — base class returns `[]` for `pos.order`; concrete models override with their own field list. The Odoo 19 base `pos.order` returns `[]` (verified via shell: `pos.order._load_pos_data_fields(config)` → `[]`). | Our override on `l10n_ve_pos/models/pos_order.py:_load_pos_data_fields` adds the Odoo 19 base contract fields (id, name, uuid, pos_reference, date_order, state, amount_total, amount_tax, amount_paid, amount_return, company_id, session_id, config_id, currency_id, pricelist_id, partner_id, lines, payment_ids) plus the Venezuelan `foreign_amount_total` and `foreign_currency_rate`. |
| `pos.order.line._load_pos_data_fields` declares per-line fields | `/home/binaural19/odoo/addons/point_of_sale/models/pos_order.py:1601-1609` — base list (qty, price_unit, tax_ids, …). | Our override on `l10n_ve_pos/models/pos_order_line.py:_load_pos_data_fields` extends the base list with `foreign_price`, `foreign_subtotal`, `foreign_total`, **`foreign_currency_rate`**. The related `foreign_currency_rate` was missing from the original `pos_order_line.py` override — that was a real Slice B gap. |
| `pos.payment._load_pos_data_fields` declares payment fields | `/home/binaural19/odoo/addons/point_of_sale/models/pos_payment.py:48-50` (domain only; the field list lives in the load mixin). | Our override on `l10n_ve_pos/models/pos_payment.py:_load_pos_data_fields` keeps the Odoo 19 core (`id`, `name`, `uuid`, `amount`, `payment_date`, `payment_method_id`, `payment_status`, `ticket`, `is_change`, `pos_order_id`, `currency_id`) — `pos_order_id` is needed by the OWL `PosPayment.setAmount` → `pos_order_id.assertEditable()` flow, hence the constant `_POS_PAYMENT_CORE_FIELDS` — and adds the Venezuelan `foreign_rate`, `foreign_amount`, `foreign_currency_id`. |
| `pos.order.read_pos_data` is the Odoo 19 read-back entry point | `/home/binaural19/odoo/addons/point_of_sale/models/pos_order.py:1297-1308` — calls `_load_pos_data_read` for `pos.order`, `pos.payment`, `pos.order.line` and returns a dict keyed by model. | The end-to-end test calls this exact method (`order.read_pos_data([], self.config)`) and asserts the read payload contains the Venezuelan foreign-currency fields. |
| `pos.order._prepare_refund_data` survives in Odoo 19 | `/home/binaural19/odoo/addons/point_of_sale/models/pos_order.py:1621-1642` — base implementation (called from `_refund()` at `:1402`). | Our override on `l10n_ve_pos/models/pos_order_line.py:_prepare_refund_data` keeps the Odoo 19 contract and adds `foreign_price` so the refund line preserves the Venezuelan value (verified by `test_pos_order_refund_copies_foreign_price_to_refund_line`). |

---

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| **Slice A** (recap, 11 tests in `test_pos_data_loading.py`) | — | Unit | N/A (new) | ✅ 5 failed on RED baseline | ✅ 11/11 | ✅ 1 added (lst_price triangulation) | ✅ Clean |
| **B.1** — `pos.order._load_pos_data_fields` includes `foreign_amount_total` / `foreign_currency_rate` | `test_pos_serialization.py::test_pos_order_load_pos_data_fields_includes_foreign_total_and_rate` | Unit | ✅ 11/11 (Slice A) | ✅ Failed: `'foreign_amount_total' not found in []` | ✅ Passed after `_load_pos_data_fields` override | ➖ Single (verified separately in B.6 round-trip) | ✅ Constants extracted |
| **B.2 / B.4** — `pos.payment._load_pos_data_fields` includes `foreign_amount` / `foreign_rate` | `test_pos_serialization.py::test_pos_payment_load_pos_data_fields_includes_foreign_amount_and_rate` | Unit | ✅ 11/11 (Slice A) | ➖ Already passing (set up in Slice A) | ✅ | ➖ Single (verified separately in B.6 round-trip) | ➖ None needed |
| **B.3 / B.4** — Dead `_export_for_ui(payment)` removed | `test_pos_serialization.py::test_legacy_serialization_hooks_are_removed` | Unit | ✅ 11/11 (Slice A) | ✅ Failed: `pos.payment` has `_export_for_ui` | ✅ Passed after override deletion | ➖ Single | ➖ None needed |
| **B.5** — `pos.order.line._load_pos_data_fields` includes `foreign_price` AND `foreign_currency_rate` | `test_pos_serialization.py::test_pos_order_line_load_pos_data_fields_includes_foreign_price_and_rate` | Unit | ✅ 11/11 (Slice A) | ✅ Failed: `'foreign_currency_rate' not found in [..., 'foreign_price', 'foreign_subtotal', 'foreign_total']` | ✅ Passed after `foreign_currency_rate` added to the override | ➖ Single (verified in B.6 round-trip) | ✅ Duplicate `PosOrderLine` class consolidated (related field, refund hook moved to `pos_order_line.py`) |
| **B.5 (refund)** — Refund line copies `foreign_price` | `test_pos_serialization.py::test_pos_order_refund_copies_foreign_price_to_refund_line` | Unit (Orm flow) | ✅ 11/11 (Slice A) | ➖ Already passing (the legacy `_prepare_refund_data` had this contract) | ✅ | ✅ Real refund flow via `order._refund()` | ➖ None needed |
| **B.6** — End-to-end round trip | `test_pos_serialization.py::test_pos_order_serialization_round_trip_preserves_foreign_fields` | Integration (read_pos_data) | ✅ 11/11 (Slice A) | ✅ Failed: `'foreign_currency_rate' not found in {... 'foreign_price': 1825.0, ...}` | ✅ Passed after B.5 | ✅ **2 lines** (one with `foreign_price=3650.0`, one with `foreign_price=1825.0`) so the read-back is verified across multiple records, not just the first | ➖ None needed |
| **B.7** — Fail-fast on legacy hook reintroduction | `test_pos_serialization.py::test_legacy_serialization_hooks_are_removed` | Unit (regression guard) | ✅ 11/11 (Slice A) | ✅ Failed: `pos.order has _order_fields` (3 hooks detected) | ✅ Passed after dead methods removed | ➖ Single (regression guard, not feature behavior) | ➖ None needed |

### Test Summary

- **Total tests written (Slice A + B)**: 11 (Slice A) + 6 (Slice B) = 17
- **Total tests passing**: 17/17 (`0 failed, 0 error(s) of 17 tests when loading database`)
- **Tests failed on RED baseline (Slice B)**: 4 (B.1 base field list, B.5 missing `foreign_currency_rate`, B.6 round trip on the same field, B.7 legacy hooks present)
- **Tests already passing on RED baseline (pre-impl Slice B)**: 2 (B.2/B.4 from Slice A; B.5 refund hook from pre-Slice-B code)
- **Tests passing on TRIANGULATE after fix**: 17/17
- **Layers used**: Unit (15), Integration / Odoo ORM read-back flow (1), Unit regression guard (1)
- **Approval tests** (refactoring): 0 — Slice B did not refactor any existing behavior; it migrated hooks and added field exposure.
- **Pure functions created**: 0 (Odoo ORM hook overrides, not pure functions)

### Strict-TDD verification evidence

```
$ DB=l10n_ve_pos_slice_b_final_1783353415
$ docker exec -u odoo proj odoo -i l10n_ve_pos --without-demo=True \
    --test-tags l10n_ve_pos --stop-after-init -d "$DB" \
    -w odoo --db_port 5432 --workers=0 --http-port=8169
…
2026-07-06 15:58:08,303 109 INFO l10n_ve_pos_slice_b_final_1783353415 odoo.service.server: 17 post-tests in 2.41s, 3412 queries
2026-07-06 15:58:08,303 109 INFO l10n_ve_pos_slice_b_final_1783353415 odoo.tests.stats: l10n_ve_pos: 21 tests 2.28s 3412 queries
2026-07-06 15:58:08,303 109 INFO l10n_ve_pos_slice_b_final_1783353415 odoo.tests.result: 0 failed, 0 error(s) of 17 tests when loading database 'l10n_ve_pos_slice_b_final_1783353415'
```

Container note: same `proj` container used in Slice A; the orchestrator prompt named `proj19`; the actual container is `proj`. Run command adjusted accordingly.

---

## Diff budget (work-unit mindset)

| Group | Files | +lines | -lines | Notes |
|-------|-------|--------|--------|-------|
| Production — `pos.order` (B.1 + B.3) | `l10n_ve_pos/models/pos_order.py` | 59 | 41 | Replaces 4 dead Odoo 17 hooks with the Odoo 19 read contract. |
| Production — `pos.order.line` (B.5) | `l10n_ve_pos/models/pos_order_line.py` | 36 | 9 | Adds `foreign_currency_rate` to the field list, moves the related field + refund hook to the canonical home, deletes the duplicate `PosOrderLine` class. |
| Production — `pos.payment` (B.2 + B.4) | `l10n_ve_pos/models/pos_payment.py` | 2 | 12 | Just deletes the dead `_export_for_ui(payment)` and the now-unused `import logging`; the Slice A `_load_pos_data_fields` override already covers B.2. |
| Test loader | `l10n_ve_pos/tests/__init__.py` | 1 | 0 | Registers the new test file. |
| **Production diff (per `git diff --numstat`)** | 4 files | **98** | **62** | **160 changed lines** — well within the 400-line review budget. |
| Tests (new file, Slice B behaviour) | `l10n_ve_pos/tests/test_pos_serialization.py` | 456 | 0 | 6 tests, strict TDD. |

### Review budget analysis

- **Production only**: 160 changed lines → **within the 400-line budget** for a single PR.
- **Production + tests**: 616 changed lines → **over** the 400-line budget.

### Split boundary (recommended if maintainer wants strict <400-line budget)

Because the test file alone is 456 lines (it carries the setUpClass scaffold for the chart-of-accounts, two-currency session, multi-line order), Slice B can be split into a feature-branch-chain of two stacked PRs if the maintainer prefers a hard <400 line per PR boundary:

| Sub-PR | Scope | Files | Lines (add+del) |
|--------|-------|-------|-----------------|
| **PR2.1** | Production migration only (B.1, B.2, B.3, B.4, B.5) | `models/pos_order.py`, `models/pos_order_line.py`, `models/pos_payment.py`, `tests/__init__.py` | **160** |
| **PR2.2** | Test coverage (B.6, B.7) | `tests/test_pos_serialization.py` | **456** |

This split does violate the `work-unit-commits` rule "Keep tests with code" — so the **default recommendation is a single PR + size:exception**, and the split is the fallback if the maintainer requires strict budget. Decision needed from reviewer.

---

## Artifacts (cumulative)

### Slice A (already in tree, recap)

- `l10n_ve_pos/tests/__init__.py` — test loader
- `l10n_ve_pos/tests/test_pos_data_loading.py` — 11 TDD tests
- `l10n_ve_pos/models/account_tax.py` — new, `_load_pos_data_fields` extension
- `l10n_ve_pos/models/product_category.py` — new, `_load_pos_data_read` parent resolver
- `l10n_ve_pos/models/__init__.py` — registered the new files
- `l10n_ve_pos/models/pos_session.py` — removed Odoo 17 patterns, added `load_data` override
- `l10n_ve_pos/models/pos_payment.py` — added `_load_pos_data_fields` (Slice A)
- `l10n_ve_pos/models/product_product.py` — added `_load_pos_data_fields` + `_load_pos_data_read`
- `l10n_ve_pos/models/res_currency.py` — added `_load_pos_data_fields` + `_load_pos_data_read`
- `l10n_ve_pos/models/res_partner.py` — added `prefix_vat` to `_load_pos_data_fields`

### Slice B (this run)

- `l10n_ve_pos/models/pos_order.py` (modified) — added `_load_pos_data_fields`, removed 4 dead Odoo 17 hooks (`_order_fields`, `_payment_fields`, `_export_for_ui(order)`, `_export_for_ui(orderline)`), consolidated the duplicate `PosOrderLine` class.
- `l10n_ve_pos/models/pos_order_line.py` (modified) — added `foreign_currency_rate` to the field list, added `_prepare_refund_data` for the refund-path preservation, declared the related `foreign_currency_rate` field.
- `l10n_ve_pos/models/pos_payment.py` (modified) — removed the dead `_export_for_ui(payment)` override.
- `l10n_ve_pos/tests/test_pos_serialization.py` (new) — 6 TDD tests for Slice B.
- `l10n_ve_pos/tests/__init__.py` (modified) — registers the new test file.

---

## Deviations from design

- **Duplicate `PosOrderLine` class consolidation** (cleanup, not a contract change): the original `pos_order.py:55-70` declared a `PosOrderLine` class that duplicated the `foreign_price` field already declared in `pos_order_line.py` and the `foreign_currency_rate` related field. The duplicate did not crash (Odoo silently keeps the last declaration), but it was confusing. Slice B moves the canonical declaration to `pos_order_line.py` and removes the duplicate from `pos_order.py`. Behavior is unchanged.
- **`_get_invoice_lines_values` signature still 2-arg** (intentional, out of scope): Odoo 19 added a third `move_type` parameter (`/home/binaural19/odoo/addons/point_of_sale/models/pos_order.py:220`). The legacy 2-arg override is preserved with a comment pointing at `tasks.md` Slice E (E.2). Forcing the 3-arg signature now would call `super()` with a missing arg, which is exactly the kind of silent contract violation the user wants avoided — but fixing it requires the invoicing flow (chart of accounts + journal), which Slice C / E owns. The defensive test `test_legacy_serialization_hooks_are_removed` does NOT cover this method because removing it would break invoicing until Slice E lands.
- **Single PR for Slice B** (size:exception): production diff is 152 lines (within budget); the test file pushes the combined change over 400. Default recommendation is single PR + `size:exception`; alternative split boundary documented above for the maintainer's choice.
- **No JS changes**: Slice B is Python-only per the design §"Slice B — Order/Payment Serialization" file map (`pos_order.py`, `pos_payment.py`, `pos_order_line.py`). The JS `export_as_JSON` patches in `static/src/overrides/models/pos_order.js:146-152` are commented out (Slice D concern).

## Issues found

- **Two `_get_invoice_lines_values` signature drift** (Odoo 19 vs. l10n_ve_pos) — left untouched, belongs to Slice E. Will crash with `TypeError` if invoicing is triggered before Slice E. Not in Slice B's read-back path.
- **`pos.order` has no base `_load_pos_data_fields`** (Odoo 19 returns `[]` from the base). Without the Slice B override, the entire `read_pos_data` payload for `pos.order` would be empty, which would silently lose every field — including Venezuelan values. This is the most impactful failure Slice B prevents. Captured in the TDD evidence (B.1 RED phase).
- **`_create_payment_moves` override** in `pos_payment.py` overrides the Odoo 19 method to write `foreign_rate` on the payment move. Signature unchanged in Odoo 19 (`/home/binaural19/odoo/addons/point_of_sale/models/pos_payment.py:72`). No Slice B action needed; verified via the existing Slice A test surface.
- **Downstream modules** in `integra-addons` (`binaural_pos_commissions`, `binaural_pos_mts_mto`, `binaural_pos_seller`, `binaural_subsidiary_pos`) still target `_order_fields` / `_export_for_ui`. Out of scope for this change but documented as the Slice C / E cleanup backlog.

## Next slice recommended

**Slice C — Session Accounting (C1 + C2, HIGH RISK)** per `tasks.md`. C1 adapts `_accumulate_amounts` / `_update_amounts` to the Odoo 19 dict shape (must keep `foreign_amount` aggregation). C2 adapts the move-creation paths (`_create_split_account_payment`, `_create_bank_payment_moves`, `_create_cash_statement_lines_and_cash_move_lines`, `_create_invoice_receivable_lines`) plus the `_get_invoice_lines_values` signature drift surfaced above. Both slices MUST be reviewed against the Odoo 19 native return types before merge (already called out in the design §3.3 "Migration Rule" + §6.2 critical controls).

**Reviewer-in-the-loop check** before Slice C starts: confirm whether the `size:exception` (single PR for Slice B) is accepted, or whether the maintainer prefers the PR2.1 + PR2.2 feature-branch-chain split.
