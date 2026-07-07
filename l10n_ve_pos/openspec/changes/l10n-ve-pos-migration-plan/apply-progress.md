# Apply Progress — l10n_ve_pos Odoo 17 → 19 Migration

**Change**: l10n-ve-pos-migration-plan
**Mode**: Strict TDD
**Module**: `l10n_ve_pos` (Odoo 19.0)
**Status**: Slice A + Slice B + Slice C1 + Slice C2.1 + Slice C2.2 + Post-Slice-B/C hotfixes (HB.1 → HD.6) complete — ⏸️ Ready to proceed with Slice C2.3 (cash statement lines)
**Last run**: 2026-07-07
**Container**: `proj`
**Run command**: `docker exec -u odoo proj odoo -i l10n_ve_pos --without-demo=True --test-tags l10n_ve_pos --stop-after-init -d l10n_ve_pos_c2_2_green_<ts> -w odoo --db_port 5432`

---

## Commits pendientes de revisión

Bandeja para que el mantenedor los repase antes de aceptar/mergear.

| Commit | Título | Motivo de revisión |
|--------|--------|--------------------|
| `78d45e01c` | `[FIX] l10n_ve_pos: corrige persistencia foreign total` | Hotfix post-Slice-B: reemplaza el hook legacy `export_as_JSON` por `serializeForORM(opts)` en el frontend (`static/src/overrides/models/pos_order.js`) para que `foreign_amount_total`/`foreign_currency_rate` viajen realmente en el sync de Odoo 19. Revisar que no falten otros callers (`export_for_printing`, `to_receipt`) y confirmar consistencia con el contrato del backend. |
| `d731aeb8e` | `[REF] l10n_ve_pos: contrato explícito de carga PoS` | Refactor previo (ya reemplazado por `e9c57b489`) que enumeraba tres tuplas de contrato en `_load_pos_data_fields`. Se mantiene en el historial como referencia de por qué se abandonó ese enfoque. |
| `e9c57b489` | `[REF] l10n_ve_pos: inyecta VE en _load_pos_data_read` | Reemplazo definitivo del anterior: mueve la extensión venezolana al hook `_load_pos_data_read`, delegando el contrato de campos al core Odoo 19. Verificar que no queden módulos downstream leyendo `foreign_amount_total`/`foreign_currency_rate` desde el field-list de `pos.order` en vez del payload de `read_pos_data`. |
| `70752aa28` | `[FEAT] l10n_ve_pos: fuerza factura obligatoria en PoS` | Regla de negocio venezolana (SENIAT): toda venta del PoS debe emitir factura. Revisar si el mantenedor quiere una vía de escape controlada (ej. permiso especial) o si la política "sin excepciones" es aceptable. |
| `f9bb592d9` | `[FIX] l10n_ve_pos: repara flujo de reembolso en PoS` | Elimina overrides muertos de v17 en `TicketScreen` y el componente `FullRefundButton` no renderizado. Revisar si se quiere reimplementar un botón "Reembolso total con un click" contra la API de Odoo 19 (queda documentado como TODO en el archivo JS). |

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

### Post-Slice-B hotfix — Order persistence hook (✅ done 2026-07-07)

- [x] **HB.1** — Fixed POS order foreign total persistence by moving custom serialization from legacy `export_as_JSON` into Odoo 19 `serializeForORM(opts)` on `PosOrder` frontend model. (`l10n_ve_pos/static/src/overrides/models/pos_order.js`)
- [x] **HB.2** — Kept receipt payload parity (`export_for_printing`) while preserving fail-fast behavior (no silent fallback to legacy sync hooks).

### Post-Slice-B refactor — pos.order load contract (✅ done 2026-07-07)

- [x] **HB.3** — Refactored `pos.order._load_pos_data_fields` to a contract-driven design: three named class-level tuples (`_ODOO19_ORDER_HEADER_FIELDS`, `_ODOO19_ORDER_SYNC_FIELDS`, `_L10N_VE_ORDER_FIELDS`) plus `_CRITICAL_LOAD_FIELDS` for the fail-fast guard. Removed the fragile `self._fields` heuristic and the loose `dependency_fields` list.
- [x] **HB.4** — Root cause traced against Odoo 19 native code: `constructOrdersDomain` in `point_of_sale/static/src/app/utils/devices_synchronisation.js` calls `record.write_date.plus(...)`, so `write_date` MUST be exposed by the `pos.order` load contract. Added `write_date` to `_ODOO19_ORDER_SYNC_FIELDS` and to `_CRITICAL_LOAD_FIELDS`, mirroring what Odoo 19 already does for `pos.order.line._load_pos_data_fields` (`pos_order.py:1608`).
- [x] **HB.5** — Added regression test `test_pos_order_load_pos_data_fields_includes_write_date` in `tests/test_pos_serialization.py` so any future change that removes `write_date` fails loudly.

### Post-Slice-B hotfix — access_token in load contract (✅ done 2026-07-07)

- [x] **HB.6** — Added `access_token` to `_ODOO19_ORDER_HEADER_FIELDS` in `pos.order._load_pos_data_fields`. Root cause verified in Odoo 19 native code: `pos_store.js::createNewOrder` sets `access_token: uuidv4()` on every new frontend order (`point_of_sale/static/src/app/services/pos_store.js:1364`), and `_process_order` pops it unconditionally on updates (`point_of_sale/models/pos_order.py:131` -> `del order['access_token']`). Without the field in the load contract, `serializeForORM` cannot round-trip it back and the backend raises `KeyError: 'access_token'` when a second sync happens against an existing draft order (e.g. adding a payment to a saved order).
- [x] **HB.7** — Added regression test `test_pos_order_load_pos_data_fields_includes_access_token` in `tests/test_pos_serialization.py`. Suite verde: 32/32 (28 executed + 4 skipped for C2.3/C2.4/C2.5 and one existing skip).

### Post-Slice-B injection — extend `_load_pos_data_read` only (✅ done 2026-07-07)

- [x] **HB.8** — Moved the Venezuelan extension from the `pos.order._load_pos_data_fields` override to `_load_pos_data_read`. The field contract stays fully owned by core Odoo 19 (we no longer enumerate `write_date`, `access_token`, `partner_id`, headers, sync fields, or critical guards). Our override loads whatever `super()._load_pos_data_read` returned and injects `foreign_amount_total` / `foreign_currency_rate` on top of it, per record. Rationale: the field-list override kept forcing us to mirror the core contract for unrelated flows (partner load domain, device sync, `_process_order`), which was reactive maintenance disguised as design.
- [x] **HB.9** — Replaced the field-listing regression tests with a behaviour-first one that exercises the real flow: `test_pos_order_load_pos_data_read_injects_foreign_total_and_rate` (creates a draft order and calls `_load_pos_data_read` to assert the foreign fields appear on the returned payload). Kept the round-trip test `test_pos_order_sync_round_trip_survives_second_sync` untouched. Suite verde: 0 failed, 0 error(s) of 32 tests.

### Post-Slice-B hotfix — Frontend UI fixes (✅ done 2026-07-07)

Series of small hotfixes discovered by running the POS UI against Odoo 19 native. Each item is a separate commit with its own `References:` link.

- [x] **HC.1** — Fixed BCV rate display in refund/order summary. `PosOrder.get_display_rate()` now normalizes inverse rates (< 1) into business format `1 foreign = X local` and `OrderSummary.getConversionRateForDisplay()` mirrors the same rule. Regression came from datasets that occasionally deliver the inverse rate; the UI must not surface it as `0.001…`. (`static/src/overrides/models/pos_order.js`, `static/src/overrides/screens/product_screen/order_summary/order_summary.js`, commit `5e477e2ca`.)
- [x] **HC.2** — Reactivated TicketScreen `OrderDisplay` bindings (`conversion_rate`, `foreign_total`, `quantity_products`, `foreign_tax`) using `get_display_rate()` so the refund screen shows the Venezuelan summary again. Odoo 19 uses `OrderDisplay`, not the legacy `OrderWidget`. (`static/src/overrides/screens/ticket_screen/ticket_screen.xml`, commit `5e477e2ca`.)
- [x] **HC.3** — Deleted the legacy XML override that replaced the native `PaymentScreen` "Invoice" button with a v17 markup relying on `useReceiptConfiguration`. Core Odoo 19 already renders the button correctly with the checkbox icon. (`static/src/overrides/screens/payment_screen/payment_screen_button.xml`, commit `1f2518134`.)
- [x] **HC.4** — Removed the JS `toggleIsToInvoice` override that still called `toggle_receipt_invoice` / `is_to_receipt` (deleted in Odoo 19). Core `PaymentScreen` uses `setToInvoice()` / `isToInvoice()` directly. (`static/src/overrides/screens/payment_screen/payment_screen.js`, commit `0b6c9afb5`.)
- [x] **HC.5** — Forced mandatory invoice on every POS order for SENIAT compliance: `PosOrder.setup()` sets `to_invoice = true` and `setToInvoice()` is locked to always keep it true. The Invoice button was removed from `PaymentScreenButtons` via inherit-mode extension so the cashier cannot toggle it off. `es_VE.po` overrides the `es_419` core translation of "Invoice" to render as "Factura" only. (`static/src/overrides/models/pos_order.js`, `static/src/overrides/screens/payment_screen/payment_screen_button.xml`, `i18n/es_VE.po`, commit `70752aa28`.)
- [x] **HC.6** — Adapted `PosOrder._get_invoice_lines_values` to the Odoo 19 signature `(line_values, pos_order_line, move_type)`. The v17 2-arg signature crashed with `TypeError: takes 3 positional arguments but 4 were given` the moment mandatory invoicing kicked in. Still injects `foreign_price` unchanged. (`models/pos_order.py`, commit `cedead22b`.)
- [x] **HC.7** — Fixed missing `is_refund` key on the invoice payments widget in two IGTF overrides. When the report engine rendered `account.report_invoice_document`, both overrides crashed with `KeyError: 'is_refund'` because they had cloned the v17 core method without the Odoo 19 additions. Both fixes now mirror the native contract (`is_refund = counterpart_line.move_id.move_type in ['in_refund', 'out_refund']`). (`l10n_ve_igtf/models/account_move.py` — commit `22057ab8e`; `integra-addons/binaural_advance_payment_igtf/models/account_move.py` — commit `624c5244e` on new branch `maint-19.0_fix-ta_73181_igtf_is_refund` off `maintenance-19.0`.)

### Post-Slice-B hotfix — Refund flow cleanup (✅ done 2026-07-07)

- [x] **HD.1** — Deleted the dead v17 refund override on `TicketScreen`: `_getToRefundDetail` / `_prepareRefundOrderlineOptions` / `addAdditionalRefundInfo` (copying the removed `to_receipt` field) all disappeared from Odoo 19. The Refund flow now delegates entirely to the native `onDoRefund` (`point_of_sale/static/src/app/screens/ticket_screen/ticket_screen.js:309`). (`static/src/overrides/screens/ticket_screen/ticket_screen.js`, commit `f9bb592d9`.)
- [x] **HD.2** — Removed the dead `FullRefundButton` component (`static/src/app/components/full_refund/full_refund.{js,xml}`) which was never rendered by any template of the module and whose internals referenced `order.orderlines` (renamed to `order.lines` in Odoo 19). Documented in the model file that a future "full refund shortcut" must be rewritten against the current API (`order.lines`, `pos.linesToRefund`). (Same commit `f9bb592d9`.)

### Post-Slice-B rollback — Retire the `delete_opening_control_session` no-op (✅ done 2026-07-07)

- [x] **HE.1** — Removed the temporary override that turned `pos.session.delete_opening_control_session` into a no-op. Introduced as a stability hotfix during the initial migration (`beforeunload` race causing `MissingError`), it was documented as pending removal in Engram (`#301 decision`, 2026-06-23). Keeping it caused orphan sessions to accumulate in `opening_control` state after every tab reload/close (verified in DB `POS`: sessions `id=6` and `id=7` without `start_at`). Native Odoo 19 already guards the delete with `if state != 'opening_control' or order_ids > 0: raise UserError` at `point_of_sale/models/pos_session.py:207`, so removing the override is safe. (`l10n_ve_pos/models/pos_session.py`.)
- [x] **HE.2** — Updated `test_delete_opening_control_session_delegates_to_core` in `tests/test_pos_data_loading.py` to assert the two branches of the native contract: an orphan `opening_control` session must delete cleanly, and a session with attached orders must raise `UserError`.

### Slice C1 — Session Accounting Accumulators (✅ done 2026-07-07)

- [x] **C1.1** — Data-key map documented at `specs/pos-odoo19-session-accounting/key-map.md`. Captures the Odoo 19 per-bucket contract (`amount` + `amount_converted`), the additive Venezuelan `foreign_amount`, and the `_get_closed_orders()` vs `self.order_ids` iteration source.
- [x] **C1.2** — `_accumulate_amounts` now uses `self._get_closed_orders()` instead of `self.order_ids` (matches Odoo 19 super). Restructured: removed the trailing `data.update({...})` (the dicts are mutated in place by `_update_amounts`); replaced the `if payment_type != "pay_later": ... [nested branches]` shape with a flat `if payment_type == "pay_later": continue` early-return; dropped the `.get(...)` default lookups in favor of `data["..."]` direct access (super always populates these keys, so the `.get(...)` was masking contract drift). (`l10n_ve_pos/models/pos_session.py`)
- [x] **C1.3** — `_update_amounts` already preserves Odoo 19 keys (`amount` / `amount_converted`) and adds `foreign_amount`; no change required, covered by the new `test_update_amounts_returns_odoo19_keys_plus_foreign_amount` test.
- [x] **C1.4** — `tests/test_pos_session_accounting_accumulators.py` (7 unit tests, all green): combine/split cash, combine/split invoice receivables, Odoo 19 key regression guard, foreign-amount aggregation across payments on the same method, and the critical ghost-entry guard (draft order with payment must NOT pollute the Odoo 19 defaultdict).
- [x] **C1.5** — Native Odoo 19 references captured in `key-map.md` §5 (per-bucket defaultdict lambdas, `_get_closed_orders()` source, `_update_amounts` round contract, Odoo 19 super return shape).

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

- **Total tests written (Slice A + B + C1)**: 11 (Slice A) + 6 (Slice B) + 7 (Slice C1) = 24
- **Total tests passing**: 24/24 (`0 failed, 0 error(s) of 24 tests when loading database`)
- **Tests failed on RED baseline (Slice B)**: 4 (B.1 base field list, B.5 missing `foreign_currency_rate`, B.6 round trip on the same field, B.7 legacy hooks present)
- **Tests failed on RED baseline (Slice C1)**: 1 (C1.2 ghost-entry test — draft order with payment polluted the Odoo 19 defaultdict)
- **Tests already passing on RED baseline (pre-impl Slice B)**: 2 (B.2/B.4 from Slice A; B.5 refund hook from pre-Slice-B code)
- **Tests passing on TRIANGULATE after fix**: 24/24
- **Layers used**: Unit (22), Integration / Odoo ORM read-back flow (1), Unit regression guard (1)
- **Approval tests** (refactoring): 0 — Slices B + C1 did not refactor any existing behavior; they migrated hooks / adapted the accumulator to the Odoo 19 dict shape.
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

## Odoo 19 native evidence (Slice C1 decisions)

| Decision | Native Odoo 19 reference | Note |
|----------|--------------------------|------|
| Odoo 19 super iterates `self._get_closed_orders()` (filters `draft` / `cancel`) | `/home/binaural19/odoo/addons/point_of_sale/models/pos_session.py:1907-1908` | The pre-C1 l10n_ve_pos override iterated `self.order_ids`, which could create ghost entries in the Odoo 19 defaultdict for non-closed orders. C1.2 fixes this. |
| Odoo 19 per-bucket default is `{'amount': 0.0, 'amount_converted': 0.0}` | `/home/binaural19/odoo/addons/point_of_sale/models/pos_session.py:847-857` (the `amounts` / `tax_amounts` lambdas) | Our `foreign_amount` MUST be additive only; super's `amount` / `amount_converted` are computed from `payment.amount` and MUST NOT be re-derived by l10n_ve_pos. |
| Odoo 19 super's `_accumulate_amounts` returns these keys (we must NOT rename or drop) | `/home/binaural19/odoo/addons/point_of_sale/models/pos_session.py:991-1009` (`data.update({...})` block) | Confirmed via `inspect.getsource`: `taxes`, `sales`, `stock_expense`, `split_receivables_bank`, `combine_receivables_bank`, `split_receivables_cash`, `combine_receivables_cash`, `combine_invoice_receivables`, `split_invoice_receivables`, `combine_inv_payment_receivable_lines`, `split_inv_payment_receivable_lines`, `split_receivables_pay_later`, `combine_receivables_pay_later`, `stock_return`, `stock_valuation`, `rounding_difference`, `MoveLine`. |
| `_update_amounts` returns a NEW dict with `amount` / `amount_converted` always present | `/home/binaural19/odoo/addons/point_of_sale/models/pos_session.py:1486-1545` | Our override extends the return dict with `foreign_amount`; we never replace the Odoo 19 keys. |
| Invoice receivables keying: split → `split_invoice_receivables[payment]`; non-split → `combine_invoice_receivables[payment_method]` | `/home/binaural19/odoo/addons/point_of_sale/models/pos_session.py:897-903` | Our override mirrors this exact keying; the new test `test_combine_invoice_receivables_keeps_foreign_amount_for_invoiced_orders` exercises the non-split branch. |

---

## TDD Cycle Evidence (Slice C1)

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| **C1.1** — Odoo 19 data-key map documented | `specs/pos-odoo19-session-accounting/key-map.md` | Doc | n/a | ➖ Single (documentation, not code) | n/a | n/a | n/a |
| **C1.2 (split cash)** — `split_receivables_cash` keeps Odoo 19 keys + adds `foreign_amount` | `test_pos_session_accounting_accumulators.py::test_split_receivables_cash_preserves_odoo19_keys_and_adds_foreign_amount` | Unit (Orm flow) | ✅ 17/17 (Slice A+B) | ➖ Already passing on the structural keys (l10n_ve_pos already extended `defaultdict` with `foreign_amount`) | ✅ Passed | ✅ 3-order helper (combined + split + invoiced) covers all four bucket types in one scenario | ✅ Lifted `_get_closed_orders()` instead of `self.order_ids` (RED-driven by the ghost-entry test) |
| **C1.2 (combine cash)** — `combine_receivables_cash` aggregates `amount` + `foreign_amount` across multiple orders | `test_pos_session_accounting_accumulators.py::test_combine_receivables_cash_preserves_odoo19_keys_and_adds_foreign_amount` | Unit | ✅ 17/17 | ➖ Already passing (initial implementation worked) | ✅ | ✅ 2 orders (1 non-invoiced + 1 invoiced) on the same method — combined `amount` = 174, combined `foreign_amount` = 6351 | ➖ None needed |
| **C1.2 (combine invoice)** — `combine_invoice_receivables` carries `foreign_amount` for invoiced orders | `test_pos_session_accounting_accumulators.py::test_combine_invoice_receivables_keeps_foreign_amount_for_invoiced_orders` | Unit | ✅ 17/17 | ➖ Already passing (initial implementation worked) | ✅ | ➖ Single (verified separately by the aggregation test) | ➖ None needed |
| **C1.2 (regression)** — NO bucket loses Odoo 19 keys after l10n_ve_pos extension | `test_pos_session_accounting_accumulators.py::test_no_receivable_bucket_loses_odoo19_keys` | Unit (regression guard) | ✅ 17/17 | ➖ Already passing | ✅ | ➖ Single (regression guard, not feature behavior) | ➖ None needed |
| **C1.2 (ghost entry)** — Draft order with payment must NOT create a ghost entry in the Odoo 19 defaultdict | `test_pos_session_accounting_accumulators.py::test_draft_order_with_payment_does_not_create_ghost_accumulator_entry` | Unit (regression guard, Odoo 19 contract) | ✅ 17/17 | ✅ **Failed**: `split_receivables_cash` had 2 entries (paid + draft); the draft payment's `foreign_amount=2117.0` created a ghost `{amount: 0, amount_converted: 0, foreign_amount: 2117.0}` that would feed C2 a zero-amount receivable | ✅ Passed after `self._get_closed_orders()` | ✅ Second case (paid + draft) makes the contract observable: with only paid orders (other tests), the bug is hidden | ✅ Replaced `self.order_ids` + `.get(...)` with `_get_closed_orders()` + `data["..."]` direct access (matches Odoo 19 super exactly) |
| **C1.3** — `_update_amounts` returns dict with Odoo 19 keys + `foreign_amount` | `test_pos_session_accounting_accumulators.py::test_update_amounts_returns_odoo19_keys_plus_foreign_amount` | Unit (pure-function-ish) | ✅ 17/17 | ➖ Already passing (initial implementation worked) | ✅ | ✅ 2nd call accumulates (100→150, foreign 3650→5475) | ➖ None needed |
| **C1.4 (aggregation)** — `foreign_amount` aggregates across multiple payments on the same method | `test_pos_session_accounting_accumulators.py::test_foreign_amount_aggregates_across_payments_for_same_method` | Unit | ✅ 17/17 | ➖ Already passing (initial implementation worked) | ✅ | ✅ 2 payments on the same method → `foreign_amount` is the sum (4234 + 4234 = 8468) | ➖ None needed |

### Test Summary (Slice C1 only)
- **Total tests written**: 7
- **Total tests passing**: 7/7
- **Layers used**: Unit (7)
- **Pure functions created**: 0 (Odoo ORM hook override, not a pure function)
- **Tests failed on RED baseline**: 1 (C1.2 ghost-entry test) — the rest passed on the existing structural contract; the refactor was driven by the C1.2 ghost-entry RED.

### Strict-TDD verification evidence (Slice C1)

```
$ DB=l10n_ve_pos_c1_full_1783437809
$ docker exec -u odoo proj odoo -i l10n_ve_pos --without-demo=True \
    --test-tags l10n_ve_pos --stop-after-init -d "$DB" \
    -w odoo --db_port 5432 --workers=0 --http-port=8169
…
2026-07-07 15:25:04,220 660 INFO l10n_ve_pos_c1_full_1783437809 odoo.service.server: 24 post-tests in 4.13s, 5014 queries
2026-07-07 15:25:04,220 660 INFO l10n_ve_pos_c1_full_1783437809 odoo.tests.stats: l10n_ve_pos: 30 tests 3.99s 5014 queries
2026-07-07 15:25:04,220 660 INFO l10n_ve_pos_c1_full_1783437809 odoo.tests.result: 0 failed, 0 error(s) of 24 tests when loading database 'l10n_ve_pos_c1_full_1783437809'
```

The `30 tests` line counts both ``-at_install`` (pre-install, counted in module load) and
``post_install`` tests; the 24 ``post-tests`` line is the one that ran our suite (17 from
Slice A+B + 7 from Slice C1).

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

### Slice C1 (this run)

- `l10n_ve_pos/openspec/changes/l10n-ve-pos-migration-plan/specs/pos-odoo19-session-accounting/key-map.md` (new) — Odoo 17 → Odoo 19 data-key map for `_accumulate_amounts`; documents the per-bucket dict shape, the additive `foreign_amount` contract, the `_get_closed_orders()` vs `self.order_ids` migration rule, and the 5-step reviewer checklist.
- `l10n_ve_pos/models/pos_session.py` (modified) — `_accumulate_amounts` now uses `self._get_closed_orders()` (was `self.order_ids`); restructured to early-return on `pay_later`; replaced `data.get("...")` with `data["..."]` (super always populates the keys); dropped the trailing `data.update({...})` (the dicts are the same `defaultdict` instances that super returned, mutated in place by `_update_amounts`). Added a contract docstring at the top of the method.
- `l10n_ve_pos/tests/test_pos_session_accounting_accumulators.py` (new) — 7 TDD tests for Slice C1: 5 contract tests (combine / split / combine-invoice / regression / aggregation) and the critical ghost-entry regression test.
- `l10n_ve_pos/tests/__init__.py` (modified) — registers the new test file.

---

## Deviations from design

- **Duplicate `PosOrderLine` class consolidation** (cleanup, not a contract change): the original `pos_order.py:55-70` declared a `PosOrderLine` class that duplicated the `foreign_price` field already declared in `pos_order_line.py` and the `foreign_currency_rate` related field. The duplicate did not crash (Odoo silently keeps the last declaration), but it was confusing. Slice B moves the canonical declaration to `pos_order_line.py` and removes the duplicate from `pos_order.py`. Behavior is unchanged.
- **`_get_invoice_lines_values` signature still 2-arg** (intentional, out of scope): Odoo 19 added a third `move_type` parameter (`/home/binaural19/odoo/addons/point_of_sale/models/pos_order.py:220`). The legacy 2-arg override is preserved with a comment pointing at `tasks.md` Slice E (E.2). Forcing the 3-arg signature now would call `super()` with a missing arg, which is exactly the kind of silent contract violation the user wants avoided — but fixing it requires the invoicing flow (chart of accounts + journal), which Slice C / E owns. The defensive test `test_legacy_serialization_hooks_are_removed` does NOT cover this method because removing it would break invoicing until Slice E lands.
- **Single PR for Slice B** (size:exception): production diff is 152 lines (within budget); the test file pushes the combined change over 400. Default recommendation is single PR + `size:exception`; alternative split boundary documented above for the maintainer's choice.
- **Hotfix crosses Slice B original file map (intentional)**: although Slice B was planned as Python-only, production evidence showed `foreign_amount_total` was still persisted as `0.0` because Odoo 19 sync uses `serializeForORM()` (frontend), not `export_as_JSON()`. We added a narrow JS hotfix in `static/src/overrides/models/pos_order.js` to align with the real Odoo 19 persistence path.

## Issues found

- **Two `_get_invoice_lines_values` signature drift** (Odoo 19 vs. l10n_ve_pos) — left untouched, belongs to Slice E. Will crash with `TypeError` if invoicing is triggered before Slice E. Not in Slice B's read-back path.
- **Odoo 19 persistence hook mismatch** — `foreign_amount_total` remained `0.0` until the frontend override moved from `export_as_JSON` to `serializeForORM()`. Evidence: Odoo 19 POS store sync path calls `order.serializeForORM({ keepCommands: true })` before `sync_from_ui`.
- **`pos.order` has no base `_load_pos_data_fields`** (Odoo 19 returns `[]` from the base). Without the Slice B override, the entire `read_pos_data` payload for `pos.order` would be empty, which would silently lose every field — including Venezuelan values. This is the most impactful failure Slice B prevents. Captured in the TDD evidence (B.1 RED phase).
- **`_create_payment_moves` override** in `pos_payment.py` overrides the Odoo 19 method to write `foreign_rate` on the payment move. Signature unchanged in Odoo 19 (`/home/binaural19/odoo/addons/point_of_sale/models/pos_payment.py:72`). No Slice B action needed; verified via the existing Slice A test surface.
- **Downstream modules** in `integra-addons` (`binaural_pos_commissions`, `binaural_pos_mts_mto`, `binaural_pos_seller`, `binaural_subsidiary_pos`) still target `_order_fields` / `_export_for_ui`. Out of scope for this change but documented as the Slice C / E cleanup backlog.
- **C1.2 ghost-entry bug** (now FIXED): pre-C1 l10n_ve_pos `_accumulate_amounts` iterated `self.order_ids` (not `self._get_closed_orders()`). A draft order with a payment would access the Odoo 19 defaultdict via `split_receivables_cash[payment]`, creating a fresh `{'amount': 0.0, 'amount_converted': 0.0}` entry. The l10n_ve_pos override then added `foreign_amount` to it, producing a ghost entry that C2's `_create_cash_statement_lines_and_cash_move_lines` would have tried to post as a zero-amount receivable. Captured in `test_draft_order_with_payment_does_not_create_ghost_accumulator_entry` (RED → GREEN via `_get_closed_orders()`).

## Diff budget (Slice C1 only)

| Group | Files | +lines | -lines | Notes |
|-------|-------|--------|--------|-------|
| Production — `pos_session.py` (C1.2) | `l10n_ve_pos/models/pos_session.py` | 78 | 51 | Refactor: `_get_closed_orders()`, early-return on `pay_later`, direct `data["..."]` access, dropped trailing `data.update`. No behavior change beyond the ghost-entry fix. |
| Production — doc artifact (C1.1) | `specs/pos-odoo19-session-accounting/key-map.md` | 137 | 0 | New doc: Odoo 17 → Odoo 19 data-key map. |
| Test loader | `l10n_ve_pos/tests/__init__.py` | 1 | 0 | Registers the new test file. |
| Tests (new file, Slice C1 behaviour) | `l10n_ve_pos/tests/test_pos_session_accounting_accumulators.py` | 596 | 0 | 7 tests, strict TDD. |
| Apply progress | `openspec/changes/.../apply-progress.md` | +~120 | -0 | Updated task list, Odoo 19 evidence, TDD cycle evidence, diff budget. |
| Tasks list | `openspec/changes/.../tasks.md` | 1 (5 `[ ]`→`[x]`) | 1 | Marked C1.1 → C1.5 as complete. |
| **Production diff (per `git diff --numstat`, production + loader only)** | 3 files | **216** | **51** | **267 changed lines — within the 400-line review budget** (key-map.md counted in this bucket because it is a planning artifact under the same `openspec/` change folder, not runtime code). |
| Tests (new file, Slice C1 behaviour) | `l10n_ve_pos/tests/test_pos_session_accounting_accumulators.py` | 596 | 0 | 7 tests, strict TDD. |

### Review budget analysis (Slice C1)

- **Production + key-map + tests loader**: 267 changed lines → **within** the 400-line budget.
- **Production + key-map + tests loader + tests**: 863 changed lines → **over** the 400-line budget.
- **Production + key-map + tests loader + tests + apply-progress + tasks**: ~990 changed lines → **over** the 400-line budget.

### Split boundary (recommended if maintainer wants strict <400-line per PR)

Because the test file alone is 596 lines (it carries the setUpClass scaffold for the chart-of-accounts, two-currency session, three-order paid+invoiced scenario), Slice C1 can be split into a feature-branch-chain of two stacked PRs if the maintainer prefers a hard <400 line per PR boundary:

| Sub-PR | Scope | Files | Lines (add+del) |
|--------|-------|-------|-----------------|
| **PR3.1** | Production refactor + key-map (C1.1, C1.2) | `models/pos_session.py`, `specs/.../key-map.md`, `tests/__init__.py` | **267** |
| **PR3.2** | Test coverage (C1.3, C1.4) | `tests/test_pos_session_accounting_accumulators.py` | **596** |

This split does violate the `work-unit-commits` rule "Keep tests with code" — so the **default recommendation is a single PR + size:exception**, and the split is the fallback if the maintainer requires strict budget. Decision needed from reviewer.

---

## Slice C2.1 — `_create_split_account_payment` return-type fix (✅ done 2026-07-07)

Scope: the single highest-risk item in Slice C2 — the Odoo 19 return-type mismatch on
`_create_split_account_payment`. C2.2 → C2.5 remain pending as the next batch.

### Completed checklist

- [x] **C2.1** — Refactored `_create_split_account_payment` (`l10n_ve_pos/models/pos_session.py:298-346`) to the Odoo 19 return contract:
  - Odoo 19 super returns an `account.move.line` recordset (the receivable line), NOT an `account.move` (native reference: `/home/binaural19/odoo/addons/point_of_sale/models/pos_session.py:1170`).
  - Reach the originating `account.payment` via `receivable_lines.move_id.origin_payment_id` — the field was renamed from `payment_id` in Odoo 19 (`/home/binaural19/odoo/addons/account/models/account_move.py:206`). The legacy chain `res.move_id.payment_id` raised `AttributeError`.
  - Handle the Odoo 19 early-return path when the payment method has no journal (native line 1147-1148): return the empty `account.move.line` recordset without touching non-existent records.
  - Preserve the Venezuelan write contract: `foreign_rate` / `foreign_inverse_rate` on the originating `account.payment`, `foreign_credit` / `foreign_debit` + `not_foreign_recalculate = True` on every line of the payment move.
- [x] **Test scaffold**: extracted the shared VES-as-foreign environment into `l10n_ve_pos/tests/test_pos_session_accounting_common.py::TestPosSessionAccountingBase` (previous phase) so C1 and C2 share ONE `setUpClass` (per the maintainer's setup-time complaint). Adjusted the base partner setup to write `property_account_receivable_id` under the test company's scope via `.with_company(cls.company).write(...)`.
- [x] **Tests (Strict TDD)**: 2 new tests in `l10n_ve_pos/tests/test_pos_session_accounting_move_creation.py`:
  1. Happy path — split-bank payment: asserts return type is `account.move.line`, receivable line has `foreign_credit == abs(payment.foreign_amount)` and `not_foreign_recalculate`, `origin_payment.foreign_rate == config.foreign_rate` (set to a distinctive `42.5` at test time so a stub implementation is forced out), and every debit/credit line on the payment move carries the matching foreign write.
  2. Triangulation — no-journal short-circuit: verifies the empty `account.move.line` recordset return without crashing. Guards against a regression that would attempt `.origin_payment_id` on the empty recordset.
- [x] **C2.2 → C2.5**: kept as `@unittest.skip` stubs in the same file with explicit "pending next batch" messages. This keeps the test file's TDD Cycle Evidence table complete for the verify phase while scoping this batch to the critical fix.

### Odoo 19 native evidence (Slice C2.1)

| Decision | Native Odoo 19 reference | Note |
|----------|--------------------------|------|
| `_create_split_account_payment` returns `account.move.line` recordset | `/home/binaural19/odoo/addons/point_of_sale/models/pos_session.py:1170` — `return account_payment.move_id.line_ids.filtered(lambda line: line.account_id == accounting_partner.property_account_receivable_id)` | Pre-C2 override treated the result as an `account.payment`-carrying move; the chain `res.move_id.payment_id` raised `AttributeError` in Odoo 19. |
| Empty-recordset early return when `payment_method.journal_id` is falsy | `/home/binaural19/odoo/addons/point_of_sale/models/pos_session.py:1147-1148` — `if not payment_method.journal_id: return self.env['account.move.line']` | Our override MUST honor this contract without touching lines that don't exist. |
| `account.move.origin_payment_id` replaces the legacy `payment_id` | `/home/binaural19/odoo/addons/account/models/account_move.py:206` — `origin_payment_id = fields.Many2one(comodel_name='account.payment', ...)` (comment: "the payment this is the journal entry of") | The Venezuelan write of `foreign_rate` / `foreign_inverse_rate` targets this `account.payment` — accessed via `move.origin_payment_id`. |

### TDD Cycle Evidence (Slice C2.1)

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| **C2.1 (happy path)** — split account payment writes foreign fields on receivable + move | `test_pos_session_accounting_move_creation.py::test_create_split_account_payment_writes_foreign_fields_on_receivable_and_move` | Unit (Odoo ORM in-process) | ✅ 24/24 (Slice A+B+C1) still pass after this change | ✅ Failed: `AttributeError: 'account.move' object has no attribute 'payment_id'` (line 302 of the pre-C2 override) | ✅ Passed after refactor to `receivable_lines.move_id.origin_payment_id` | ✅ Multi-assertion pass: return type + receivable line + `origin_payment` + every credit/debit line on the payment move | ✅ Extracted `payment_move = receivable_lines.move_id`, hoisted `foreign_amount = abs(payment.foreign_amount)` (constant per call), added Odoo 19 contract docstring |
| **C2.1 (edge case)** — no-journal short-circuit returns empty `account.move.line` recordset | `test_pos_session_accounting_move_creation.py::test_create_split_account_payment_returns_empty_recordset_when_journal_missing` | Unit (Odoo ORM in-process) | ✅ 24/24 | ✅ Failed: same `AttributeError` — the empty-recordset path also hit `res.move_id.payment_id` | ✅ Passed after adding `if not receivable_lines: return receivable_lines` guard | ✅ Second scenario (no-journal) is a real behavioral branch, not a rerun of the happy path — different setup, different code path exercised | ➖ None needed |

### Test Summary (Slice C2.1 only)

- **Total tests written**: 2 (C2.1 happy path + C2.1 no-journal edge case)
- **Total tests passing**: 2/2 (both went RED → GREEN in this batch)
- **Skipped in this batch** (pending next batch): 4 (C2.2, C2.3, C2.4, C2.5)
- **Full suite result**: `0 failed, 0 error(s) of 30 tests` (26 executed + 4 skipped)
- **Layers used**: Unit — Odoo ORM in-process
- **Pure functions created**: 0 (Odoo ORM hook override, not a pure function)
- **Refactor step**: hoisted `foreign_amount = abs(payment.foreign_amount)` out of the loop (constant per call) and split `receivable_lines.move_id` into a local `payment_move` so the two accesses (`origin_payment_id` and `line_ids`) share a single traversal.

### Strict-TDD verification evidence (Slice C2.1)

```
$ DB=l10n_ve_pos_c2_1_full_1783442086
$ docker exec -u odoo proj odoo -i l10n_ve_pos --without-demo=True \
    --test-tags l10n_ve_pos --stop-after-init -d "$DB" \
    -w odoo --db_port 5432 --workers=0 --http-port=8170
…
2026-07-07 16:35:59,334 71 INFO l10n_ve_pos_c2_1_full_1783442086 odoo.service.server: 30 post-tests in 4.81s, 6143 queries
2026-07-07 16:35:59,335 71 INFO l10n_ve_pos_c2_1_full_1783442086 odoo.tests.stats: l10n_ve_pos: 38 tests 4.67s 6143 queries
2026-07-07 16:35:59,335 71 INFO l10n_ve_pos_c2_1_full_1783442086 odoo.tests.result: 0 failed, 0 error(s) of 30 tests when loading database 'l10n_ve_pos_c2_1_full_1783442086'
```

### Diff budget (Slice C2.1)

| Group | Files | +lines | -lines | Notes |
|-------|-------|--------|--------|-------|
| Production — `pos_session.py` (C2.1) | `l10n_ve_pos/models/pos_session.py` | 42 | 15 | Refactored `_create_split_account_payment` to Odoo 19 return contract; added contract docstring. |
| Test scaffold (shared) | `l10n_ve_pos/tests/test_pos_session_accounting_common.py` | 6 | 12 | Simplified partner-setup write to use `.with_company(cls.company)` idiomatically. |
| Tests (new file, C2.1 behaviour) | `l10n_ve_pos/tests/test_pos_session_accounting_move_creation.py` | 234 | 0 | 2 active TDD tests + 4 `@unittest.skip` stubs for the pending sub-slices. |
| Test loader | `l10n_ve_pos/tests/__init__.py` | 2 | 0 | Registers the new common + move-creation test modules. |
| Tasks list | `openspec/changes/.../tasks.md` | 1 | 1 | Marked C2.1 as `[x]`. |
| Apply progress | `openspec/changes/.../apply-progress.md` | +~100 | -0 | Added the Slice C2.1 section. |

### Deviations from design (Slice C2.1)

- **`.with_company()` at the call site** (not global env change): the C2 tests need `env.company == test_company` when reading `partner.property_account_receivable_id`. Attempting to switch it globally (via `env.user.company_id` write or an `su=True` re-bound env) cascades into unrelated ORM recomputes (a `supplier_taxes_rel` datatype mismatch surfaces in the current test environment). The pragmatic fix is per-call `.with_company(self.company)` on both `session` AND `payment` — payment inherits its env from creation-time and `_find_accounting_partner(payment.partner_id)` reads properties through the passed partner's env, not `self.env`. Documented in the test file so C2.2 can reuse the pattern.
- **Skip decorators for C2.2 → C2.5**: keeps the file's structure ready for the next batch while giving the verify phase an explicit signal that these are pending, not accidentally missing. Skips DO count as executed tests in the Odoo runner, so the summary line still reflects the full test surface.

### Issues found (Slice C2.1)

- **Legacy `res.move_id.payment_id` chain would have crashed at close-session time** in Odoo 19. This is not a "silent contract violation" — it's a `AttributeError` blocker that would prevent any split-account payment from being closed. Fixed here.
- **Test-env company crossover**: `res.partner.property_account_receivable_id` is a company-dependent field; without a fixed env.company, the accounting-partner lookup crosses companies and Odoo 19 `_check_company` on `account.payment.create` refuses the move. The workaround (`.with_company()` at the call site) is applied consistently across the two active C2.1 tests and will need to be re-applied in C2.2 → C2.5 when they wake up.
- **Duplicate `_build_session_with_paid_orders` helper**: the pre-existing C2 test skeleton (from the previous batch, uncommitted) referenced a `_build_session_with_paid_orders` method local to `TestPosSessionAccountingMoveCreation`. In this batch we removed it because C2.1 doesn't need the four-order scenario (it hits the split-bank path in isolation with one order). C2.2 → C2.5 will re-add a lean version scoped to their specific needs when they wake up.

## Slice C2.2 — `_create_bank_payment_moves` verified against Odoo 19 (✅ done 2026-07-07)

Scope: adapt `_create_bank_payment_moves` to the Odoo 19 return contract and
close the C2.2 stub in `test_pos_session_accounting_move_creation.py`. The
tasks planning note "re-map `payment_to_receivable_lines` keys" turned out
to be a false alarm once the Odoo 19 native code was read line-by-line:
Odoo 19 super keeps the same keying as Odoo 17 (`pos.payment.method` for
combine, `pos.payment` records for split) — see native reference below.
The real work in this slice was (a) proving the contract with an end-to-end
test that exercises BOTH branches, and (b) collapsing the two duplicated
credit/debit loops into a single helper so future accountants can find the
Venezuelan write in exactly one place.

### Completed checklist

- [x] **C2.2** — `_create_bank_payment_moves` (`l10n_ve_pos/models/pos_session.py:581`):
  - Verified Odoo 19 native return contract via
    `/home/binaural19/odoo/addons/point_of_sale/models/pos_session.py:1050-1072`:
    the method MUTATES `data` in-place and returns the same dict; keying
    is unchanged from Odoo 17.
  - Replaced the legacy `res = super(); res.get(...)` pattern with the
    idiomatic Odoo 19 `data = super(); data["..."]` (super never omits
    those keys, so the `.get()` was masking contract drift the same way
    it did in C1.2).
  - Extracted the duplicated `for line in lines: if credit/debit: write`
    logic into `_set_foreign_amount_on_receivable_lines(lines, foreign_amount)`
    so combine and split both go through one code path.
  - Added a contract docstring documenting the two buckets, the value
    shape (union of session-side receivable + payment-move receivable),
    and the additive Venezuelan write.
- [x] **Test scaffold**: reused `TestPosSessionAccountingBase` from
  `l10n_ve_pos/tests/test_pos_session_accounting_common.py` (same
  `setUpClass` that C1 and C2.1 already use — zero additional setup cost
  per the maintainer's setup-time complaint).
- [x] **Test (Strict TDD)**: enabled the previously skipped
  `test_create_bank_payment_moves_writes_foreign_fields_on_receivable_lines`
  in `test_pos_session_accounting_move_creation.py`:
  - Builds ONE combined-bank order + ONE split-bank order in the shared
    session, then replicates the first three lines of
    `_create_account_move` (session_move seed + `_accumulate_amounts`)
    and jumps straight into `_create_bank_payment_moves`.
  - Asserts the Odoo 19 keying contract on BOTH buckets
    (`pos.payment.method` for combine, `pos.payment` for split).
  - Asserts `foreign_credit`/`foreign_debit` and
    `not_foreign_recalculate=True` on every receivable line in both
    buckets — the two branches ARE the triangulation.
  - Distinctive `foreign_rate=42.5` at test time rules out any hardcoded
    Fake It path.

### Odoo 19 native evidence (Slice C2.2)

| Decision | Native Odoo 19 reference | Note |
|----------|--------------------------|------|
| `_create_bank_payment_moves` mutates `data` in place and returns the SAME dict | `/home/binaural19/odoo/addons/point_of_sale/models/pos_session.py:1070-1072` — `data['payment_method_to_receivable_lines'] = ...`, `data['payment_to_receivable_lines'] = ...`, `return data` | The old pattern (`res = super(); res.get(...)`) worked by accident because `res is data`. Migrated to the idiomatic `data = super(); data["..."]` for clarity and to match the C1 refactor. |
| Combine bucket keyed by `pos.payment.method` | Native line 1057-1060 — `for payment_method, amounts in combine_receivables_bank.items(): ... payment_method_to_receivable_lines[payment_method] = ...` | Odoo 19 uses the SAME keying as Odoo 17. The tasks-plan note about "re-mapping keys" was speculative and turned out to be unnecessary once the Odoo 19 source was inspected. |
| Split bucket keyed by `pos.payment` records | Native line 1062-1065 — `for payment, amounts in split_receivables_bank.items(): ... payment_to_receivable_lines[payment] = ...` | Same as above — no key rename in Odoo 19. Our override reads `payment.foreign_amount` (direct attribute) rather than `payment["foreign_amount"]` for clarity; both are equivalent because `pos.payment.__getitem__` proxies to the field. |
| Value shape: union of two `account.move.line` records | Native line 1058-1060 — `combine_receivable_line | payment_receivable_line`; native line 1063-1065 — `split_receivable_line | payment_receivable_line` | Our helper iterates the union so both the session-side receivable (created in this method) and the payment-move receivable (created by `_create_combine_account_payment` / `_create_split_account_payment`) get their Venezuelan write. |
| `_create_combine_account_payment` return is `account.move.line` (receivable line) | Native line 1120 — `return account_payment.move_id.line_ids.filtered(lambda line: line.account_id == self._get_receivable_account(payment_method))` | Confirms the union-of-two-move-lines shape holds symmetrically for combine and split (C2.1 already handled the split return contract). |

### TDD Cycle Evidence (Slice C2.2)

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| **C2.2** — `_create_bank_payment_moves` writes foreign fields on both combine + split receivable buckets | `test_pos_session_accounting_move_creation.py::test_create_bank_payment_moves_writes_foreign_fields_on_receivable_lines` | Unit (Odoo ORM in-process) | ✅ 30/30 (Slice A+B+C1+C2.1) still pass after this change | ✅ Failed: `psycopg2.errors.NotNullViolation: null value in column "date" of relation "account_move"` (scaffold gap — `session.stop_at` / `start_at` are null for an unposted session; fixed by seeding `date` with `fields.Date.context_today(session)`) | ✅ Passed after the scaffold fix — confirmed the current override IS already Odoo 19-compatible | ✅ Both branches exercised in ONE test: combine (keyed by `pos.payment.method`) and split (keyed by `pos.payment`) — a regression on either accessor would fail; distinctive `foreign_rate=42.5` rules out Fake It | ✅ Collapsed two duplicated credit/debit loops into `_set_foreign_amount_on_receivable_lines(lines, foreign_amount)`; migrated from `res.get(...)` to `data["..."]` (idiomatic Odoo 19); added contract docstring |

**Transparency note on the RED**: the RED came from the test scaffold
(nullable `date` on the session_move seed), not from the production
override. The override was **already correct** after C1+C2.1 landed — no
functional regression to fix. The **new value** delivered by this slice
is: (a) an end-to-end regression guard that would fail if a future
refactor drifted the combine or split accessors, (b) removal of the
duplicated credit/debit block in favor of one helper, and (c) explicit
Odoo 19 evidence recorded here for the reviewer. This is the strict-TDD
"function already exists → test the NEW behavior not yet implemented"
path: the new behavior is the observable regression guard.

### Test Summary (Slice C2.2 only)

- **Total tests written**: 1 (enabled from the skip stub)
- **Total tests passing**: 1/1
- **Skipped in this batch** (pending next batch): 3 (C2.3, C2.4, C2.5)
- **Full suite result**: `0 failed, 0 error(s) of 31 tests` (28 executed + 3 skipped)
- **Layers used**: Unit — Odoo ORM in-process
- **Pure functions created**: 0 (Odoo ORM hook override, not a pure function)
- **Refactor step**: extracted `_set_foreign_amount_on_receivable_lines` (single write path); migrated `res.get(...)` → `data["..."]` to match the C1 refactor.

### Strict-TDD verification evidence (Slice C2.2)

```
$ DB=l10n_ve_pos_c2_2_green_1783444991
$ docker exec -u odoo proj odoo -i l10n_ve_pos --without-demo=True \
    --test-tags l10n_ve_pos --stop-after-init -d "$DB" \
    -w odoo --db_port 5432 --workers=0 --http-port=8173
…
2026-07-07 17:24:41,943 INFO odoo.service.server: 31 post-tests in 5.28s, 6453 queries
2026-07-07 17:24:41,943 INFO odoo.tests.stats: l10n_ve_pos: 39 tests 5.15s 6453 queries
2026-07-07 17:24:41,943 INFO odoo.tests.result: 0 failed, 0 error(s) of 31 tests
```

### Diff budget (Slice C2.2)

| Group | Files | +lines | -lines | Notes |
|-------|-------|--------|--------|-------|
| Production — `pos_session.py` (C2.2) | `l10n_ve_pos/models/pos_session.py` | 45 | 21 | Rewrote `_create_bank_payment_moves` with contract docstring + Odoo 19 idiomatic `data[...]`; added `_set_foreign_amount_on_receivable_lines` helper. |
| Tests (enabled stub, C2.2 behaviour) | `l10n_ve_pos/tests/test_pos_session_accounting_move_creation.py` | ~180 | 3 | Replaced the `@unittest.skip` stub with the real regression test; added `from odoo import fields`. |
| Tasks list | `openspec/changes/.../tasks.md` | 1 | 1 | Marked C2.2 as `[x]`. |
| Apply progress | `openspec/changes/.../apply-progress.md` | +~150 | -0 | Added the Slice C2.2 section. |
| **Production diff (per `git diff --numstat`, production only)** | 1 file | **45** | **21** | **66 changed lines** — well within the 400-line review budget. |
| Production + test | 2 files | ~225 | 24 | ~249 changed lines — within budget for a work-unit commit. |

### Deviations from design (Slice C2.2)

- **`payment["foreign_amount"]` → `payment.foreign_amount`**: cosmetic
  cleanup while refactoring. Both forms are equivalent because
  `pos.payment.__getitem__(str)` proxies to the field getter (verified in
  `/home/binaural19/odoo/odoo/orm/models.py:6674-6688`). The attribute
  form is clearer at the call site and matches how C2.1 accesses the
  same field.
- **Task-plan note "re-map keys" turned out to be a false alarm**: after
  reading Odoo 19 native code line-by-line, the keying is unchanged from
  Odoo 17. Recorded transparently in the Odoo 19 evidence table above so
  future reviewers don't reintroduce a fictitious rename.

### Issues found (Slice C2.2)

- **Test scaffold gap (fixed here)**: `session.stop_at` and
  `session.start_at` are null for an unposted session; seeding the
  session's `account.move` with either of those directly triggers a
  `NotNullViolation`. Fixed by using `fields.Date.context_today(session)`.
  This is scaffolding lore that C2.3 (cash statement lines) will need to
  reuse — noted here rather than being rediscovered next slice.
- **Duplicate credit/debit loops (fixed here)**: the pre-C2.2 override
  had two near-identical loops, one per bucket, each with its own
  `if credit / if debit` branching. That structure invited copy-paste
  drift (imagine one branch reading `foreign_credit`, the other
  `foreign_debit`). Centralized in `_set_foreign_amount_on_receivable_lines`.

## Next slice recommended

**Slice C2.3 — `_create_cash_statement_lines_and_cash_move_lines`**. Depends on: nothing further (C2.2 done). Remaining C2 items:

- `_create_cash_statement_lines_and_cash_move_lines` (`pos_session.py::_create_cash_statement_lines_and_cash_move_lines`): re-map response dict; keep `set_foreign_amount_in_line` helper.
- `_create_invoice_receivable_lines` (`pos_session.py::_create_invoice_receivable_lines`): align to `combine_inv_payment_receivable_lines` record sets; preserve foreign aggregation.
- `_create_payment_moves` (`pos_payment.py::_create_payment_moves`): foreign-field writes on matching move; float-compare filter still valid.

The 3 remaining `@unittest.skip` stubs in `test_pos_session_accounting_move_creation.py` mark exactly these targets; they read from the C1 accumulator data-key map (`specs/pos-odoo19-session-accounting/key-map.md`).
