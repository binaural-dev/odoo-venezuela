# Proposal: l10n_ve_pos Odoo 17 → 19 Migration Plan

## Intent

`l10n_ve_pos` still uses Odoo 17 POS APIs and blocks 15+ downstream modules already stamped 19.0.1.0.0 (`l10n_ve_pos_igtf`, `l10n_ve_pos_mf`, and 14 `integra-addons` modules). Odoo 19 removed `load_pos_data`, `_order_fields`, `_payment_fields`, and `_export_for_ui`, and changed session-closing accounting structures. This change produces the migration plan, specs, design, and tasks so implementation can proceed in small, safe slices.

## Scope

### In Scope
- Migration plan for `l10n_ve_pos` to Odoo 19 patterns.
- Delta specs for the 5 critical gaps.
- Design for `_load_pos_data_*` mapping and accounting dict adaptation.
- Phased task list sized for ≤400-line review budget.
- Acceptance criteria, success metrics, and risk register.

### Out of Scope
- Runtime code edits to `l10n_ve_pos` or downstream modules.
- Implementation, testing, or deployment of the migration.
- Dead-code cleanup outside the migration path.
- POS IoT, Enterprise, or non-Venezuelan modules.

## Capabilities

### New
- `pos-odoo19-data-loading`: Replace `load_pos_data` / `_loader_params_*` with `load_data` / `_load_pos_data_*`.
- `pos-odoo19-serialization`: Replace `_order_fields`, `_payment_fields`, `_export_for_ui` with `_load_pos_data_*`.
- `pos-odoo19-session-accounting`: Adapt `_accumulate_amounts`, `_create_split_account_payment`, `_create_bank_payment_moves`, `_create_cash_statement_lines_and_cash_move_lines`, and `_create_invoice_receivable_lines` to Odoo 19 dict/record structures.
- `pos-odoo19-frontend`: Re-enable JS foreign-currency patches.

### Modified
- None. Planning-only; runtime deltas will be spec'd separately.

## Approach

Use the exploration gap analysis as source of truth. Split migration into 5 slices ordered by dependency and risk: data loading → order/payment serialization → session accounting → JS cleanup → verification & polish. Each slice becomes one implementation change. Keep every commit under 400 changed lines; split the accounting slice further if needed.

## Affected Areas

| Area | Impact |
|------|--------|
| `openspec/changes/l10n-ve-pos-migration-plan/specs/` | New delta specs |
| `openspec/changes/l10n-ve-pos-migration-plan/design.md` | New design |
| `openspec/changes/l10n-ve-pos-migration-plan/tasks.md` | New task breakdown |
| `src/odoo-venezuela/l10n_ve_pos/` | Read-only reference |

## Risks

| Risk | Level | Mitigation |
|------|-------|------------|
| `_accumulate_amounts` dict mismatch causes wrong accounting entries | High | Model before/after structures; verify with real multi-currency orders |
| `_create_split_account_payment` return-type change silently breaks payments | High | Trace call chain; add type assertion in design |
| Downstream modules blocked past 19.0 release | Med | Prioritize Slice 1+2 for early compatibility |
| Dead JS patches break VES/USD UI → backend flow | Med | Include JS re-enablement as explicit slice |

## Rollback Plan

Only planning artifacts are created. Rollback is `git revert`. No runtime or database impact.

## Dependencies

- Odoo 19.0 reference at `/home/binaural19/odoo/addons/point_of_sale/`.
- `l10n_ve_pos` source in `src/odoo-venezuela` (branch 19.0).
- Review from owners of downstream modules.

## Success Criteria

- [ ] All planning artifacts exist.
- [ ] Every critical gap has an objective and acceptance criteria.
- [ ] Each slice is ≤400 changed lines or explicitly split.
- [ ] Accounting high-risk areas have verification scenarios.
- [ ] Downstream blockers are mapped with priority.
- [ ] Artifacts are reviewed and approved.
