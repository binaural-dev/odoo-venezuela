# Dispatch Guide Control Number (Pre-Printed Stationery)

> **Organization**: binaural-dev
> **Author**: Binaural Claude
> **Tarea**: 80614
> **Status**: implemented, pending task ID / merge

## Intent

Give the dispatch guide a third, independent way to satisfy the SENIAT
"Número de Control" requirement: a number pre-printed by an authorized
printer on the physical stationery, recorded in Odoo for traceability only
— never generated or printed by the system.

This is not exclusive to any one client. `l10n_ve_stock_account` already
resolves the same legal requirement two other ways for different documents:
`account.move.correlative` (own sequence, `l10n_ve_invoice`) and
`stock.picking.control_number_tfhka` (digital provider,
`l10n_ve_invoice_digital`). Pre-printed stationery is a third, common
Venezuelan invoicing method, so it belongs at the same layer as those two,
not duplicated per client.

## Scope

### In scope
- One reserved control number per printed sheet of a dispatch guide
  (`stock.picking.control.number.line`, one2many from `stock.picking`).
- A company-scoped setting for how many product lines fit on one sheet.
- Reservation happens once, at `_action_done`, gated by the same
  `dispatch_guide_controls` condition that already gates `guide_number`.

### Out of scope
- The dispatch guide's print layout/pagination — a separate, already
  proposed change in `lagiralda_stock`
  ([`lagiralda-stock-report-formats`](../../../../lagiralda_stock/openspec/changes/lagiralda-stock-report-formats/proposal.md)).
  The control number is recorded, not printed (it is already on the
  physical paper).
- The `guide_number` sequence itself (`get_sequence_guide_num`) — unchanged.
  Investigated whether it needed per-client namespacing (`code` collision
  between two different clients' `ir.sequence` records); this project's
  runtime provisions one dedicated Postgres database per client instance
  (`db_filter`, dedicated role, `REVOKE CONNECT` from `PUBLIC` — see
  `instances.json`), so two different clients' sequences can never share a
  table to collide in. The only real collision surface is between two
  `res.company` records in the *same* database, and that is already
  resolved by the existing `company_id` domain on `get_sequence_guide_num`.
  No namespacing added.

## Capabilities

| Module | Capability | Change |
|---|---|---|
| `l10n_ve_stock_account` | `dispatch-guide-control-number` | ADDED |

## Approach

**Model.** `stock.picking.control.number.line` (`picking_id`, `sheet_number`,
`number`), not a comma-separated string on `stock.picking`. A comma-joined
`Char` is not queryable, has no referential integrity, and cannot be
filtered/audited per company through a normal `ir.rule`. A child record per
sheet is.

**Sheet count.** `ceil(len(move_line_ids) / max_lines)`, with a floor of 1
sheet (a guide with zero lines still gets one control number — the paper is
consumed regardless). `max_lines` is read once per picking from the
picking's own company.

**Setting.** `res.company.dispatch_guide_control_number_max_lines`
(`Integer`, default `15`), mirrored in `res.config.settings` — the exact
same "plain field on `res.company` + related field in settings" pattern
already used in this module for `indexed_dispatch_guide`,
`hide_disc_field_dispatch_guide`, etc. **Not** a global
`ir.config_parameter` (the reference sketch for this feature used one,
which is a bug for any multi-company install: two companies sharing paper
stock with a different line count would silently share one value). Also
**not** `company_dependent=True`: that ORM mechanism is for fields on
*other* models that need to vary by the *current* company context: a field
declared directly on `res.company` is already inherently per-company, so
`company_dependent=True` there would be redundant.

**Sequence.** Same search-or-create pattern as `get_sequence_guide_num`
(`code="stock.picking.control.number"`, `company_id` domain), so it is
isolated per company for the same reason `guide_number`'s sequence is.

**Gating & hook.** Reuses `dispatch_guide_controls` (no new condition to keep
in sync with `guide_number`'s). `_action_done` calls
`self._assign_control_numbers()` right after the existing
`self._set_guide_number()` call, via `super()`, so it doesn't interfere with
`l10n_ve_invoice_digital`'s full override of `_set_guide_number` (TFHKA
path) — the two features are independent and neither calls the other.

## Affected areas

| Area | File |
|---|---|
| Model | `models/stock_picking_control_number_line.py` (new) |
| Model | `models/stock_picking.py` (`control_number_ids`, `_get_control_number_max_lines`, `_get_control_number_sequence`, `_assign_control_numbers`, `_action_done`) |
| Model | `models/res_company.py`, `models/res_config_settings.py` |
| Security | `security/ir.model.access.csv`, `security/ir_rule.xml` (new — multi-company isolation) |
| Views | `views/stock_picking_views.xml`, `views/res_config_setting_views.xml` |
| Tests | `tests/test_stock_picking_control_number.py` (new) |

## Risks

- **`move_line_ids` at `_action_done` time.** The sheet count reads
  `move_line_ids` after `super()._action_done()` has run, so quantities are
  final — same assumption `guide_number` already relies on for this hook.
- **Idempotency.** `_assign_control_numbers` skips pickings that already
  have `control_number_ids`, mirroring the "never overwrite" guard on
  `guide_number`. A picking cannot be re-validated into a second set of
  control numbers.

## Rollback

Revert the commit. `control_number_ids` and the setting become orphaned but
harmless (no other capability reads them). No data migration needed; the
new sequence and model are additive.

## Dependencies

None beyond what `l10n_ve_stock_account` already depends on.

## Success criteria

1. A dispatch guide with fewer lines than the configured maximum reserves
   exactly one control number.
2. A guide with more lines than the maximum reserves one number per full or
   partial sheet (`ceil`), never zero.
3. Two companies with different maximums never cross sheet counts or
   sequence numbers.
4. Re-running `_action_done` on an already-controlled picking does not
   reserve additional numbers.
5. `guide_number` assignment (existing behaviour) is unaffected.
