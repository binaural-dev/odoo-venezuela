# Tasks — Dispatch Guide Control Number

> **Ticket**: PENDIENTE (asignar antes de push/PR)

## Implementation

- [x] `stock.picking.control.number.line` model (`picking_id`, `sheet_number`, `number`, `company_id` related).
- [x] `stock.picking.control_number_ids` (One2many) + `_get_control_number_max_lines`, `_get_control_number_sequence`, `_assign_control_numbers`.
- [x] Hook `_assign_control_numbers()` into `_action_done`, after `_set_guide_number()`, via `super()`.
- [x] `res.company.dispatch_guide_control_number_max_lines` (default 15) + related field in `res.config.settings`.
- [x] Settings view (`res_config_setting_views.xml`).
- [x] Picking form view: read-only `control_number_ids` list next to `guide_number`.
- [x] ACL for the new model (`security/ir.model.access.csv`).
- [x] Multi-company `ir.rule` for the new model (`security/ir_rule.xml`, new file).
- [x] Bump manifest (`19.0.2.0.4` → `19.0.2.0.5`).

## Verification

- [x] 0 lines → 1 sheet.
- [x] 1 line → 1 sheet.
- [x] exactly `max_lines` → 1 sheet.
- [x] `max_lines + 1` → 2 sheets.
- [x] exact multiple of `max_lines` → exact sheet count, no extra.
- [x] different `max_lines` per company never cross.
- [x] default `max_lines` (15) when unset on a company.
- [x] re-running `_assign_control_numbers` on an already-controlled picking is a no-op.
- [x] sequence isolated per company (search-or-create).
- [x] `guide_number` assignment still happens alongside control numbers (regression guard).
- [x] `./odoo test giralda l10n_ve_stock_account,lagiralda_stock,lagiralda_account --out-coverage-json` — see `tasks.md` companion report in the client repo for the combined run result.

## Pending

- [ ] Decide/confirm Tarea ID before push/PR (currently PENDIENTE).
- [ ] **Pre-existing, unrelated finding surfaced by this change's test run**:
      `integra-addons/binaural_subsidiary_stock`'s `stock.picking.get_customer_journal()`
      override calls `self.ensure_one()` unconditionally, which breaks on an
      empty recordset. It only surfaces when `binaural_subsidiary_stock` is
      installed alongside `l10n_ve_stock_account` (it is not part of this
      module's own dependency tree, and its own isolated test suite passes
      cleanly — confirmed via `./odoo test giralda l10n_ve_stock_account`
      alone: 0 failures). It very likely already reproduces in Giralda's
      real database today, independent of this change; it is **not fixed
      here** (different module, different owner) but is left flagged for a
      human to triage. 11 pre-existing test errors in
      `l10n_ve_stock_account`'s own suite (`test_create_invoice.py`,
      `test_stock_picking.py::test_get_customer_journal`,
      `test_wizards.py`) trace back to this same root cause.

## OpenSpec

- [x] `proposal.md` + spec delta (`dispatch-guide-control-number`)
