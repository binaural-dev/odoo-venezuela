# l10n_ve_pos Odoo 19 Migration Planning Specification

## Purpose

Define the planning-only requirements for the `l10n_ve_pos` Odoo 17 → 19 migration plan, including API mapping coverage, commit granularity, downstream blocker visibility, and non-goals.

## Requirements

### Requirement: Map every Odoo 17 POS API to Odoo 19

The migration plan MUST contain a mapping table that lists every Odoo 17 POS API symbol used by `l10n_ve_pos` and the corresponding Odoo 19 API, with source file and line references.

#### Scenario: Mapping table covers old data-loading APIs

- GIVEN the source tree of `src/odoo-venezuela/l10n_ve_pos`
- WHEN the reviewer searches for `load_pos_data`, `_loader_params_*`, `_get_pos_ui_*`, `_pos_ui_models_to_load`
- THEN each match appears in the mapping table with an Odoo 19 replacement

#### Scenario: Mapping table covers serialization and accounting APIs

- GIVEN the same source tree
- WHEN the reviewer searches for `_order_fields`, `_payment_fields`, `_export_for_ui`, `_accumulate_amounts`, `_create_split_account_payment`, `_create_bank_payment_moves`, `_create_cash_statement_lines_and_cash_move_lines`, and `_create_invoice_receivable_lines`
- THEN each match appears in the table with an Odoo 19 replacement

### Requirement: Commit-slice granularity

The plan MUST decompose implementation into slices where each slice produces no more than 400 changed lines (additions + deletions). Any slice that cannot meet the budget MUST be split and the split MUST be justified.

#### Scenario: Slice line budgets are visible

- GIVEN `tasks.md`
- WHEN the reviewer inspects each slice
- THEN each slice has a forecast line count and a status of `within budget` or `split required`

#### Scenario: Accounting slice is split if needed

- GIVEN the accounting slice forecast
- WHEN its line count exceeds 400
- THEN the plan splits it into smaller sub-slices with clear boundaries

### Requirement: Downstream blocker visibility

The plan MUST list all downstream modules blocked by `l10n_ve_pos` and identify which migration slice removes the blocker.

#### Scenario: Blocker list is complete

- GIVEN the proposal's risk register
- WHEN the reviewer checks the downstream module list
- THEN `l10n_ve_pos_igtf`, `l10n_ve_pos_mf`, and the 14 `integra-addons` modules are listed with priority

#### Scenario: Slices unblock downstream work

- GIVEN the task list
- WHEN the reviewer inspects dependencies
- THEN Slice 1 and Slice 2 are marked as unblocking downstream module migration

### Requirement: Define non-goals and constraints

The plan MUST explicitly state what is out of scope: runtime code edits to `l10n_ve_pos` or downstream modules, implementation/testing/deployment, dead-code cleanup outside the migration path, and POS IoT/Enterprise/non-Venezuelan modules.

#### Scenario: Non-goals are documented

- GIVEN the migration plan
- WHEN the reviewer reads the scope section
- THEN the non-goals above are listed and no runtime code change is requested

#### Scenario: Runtime code remains untouched

- GIVEN the change folder
- WHEN the reviewer checks the diff
- THEN no Python or JS file in `src/` is modified

### Requirement: Provide reviewability artifacts

The plan MUST include acceptance criteria, success metrics, a risk register, and a rollback plan.

#### Scenario: Acceptance criteria are testable

- GIVEN the acceptance criteria section
- WHEN the reviewer reads each item
- THEN each item can be verified by inspecting the produced artifacts or running a check

#### Scenario: Rollback plan is documented

- GIVEN the risk register
- WHEN a high-risk assumption fails
- THEN the rollback plan describes how to revert without runtime or database impact

### Requirement: Slice dependency order

The plan MUST order slices as: data loading → serialization → session accounting → frontend cleanup → verification & polish.

#### Scenario: Dependency graph is acyclic

- GIVEN the task list
- WHEN the reviewer draws the slice dependency graph
- THEN no cycle exists and each slice's inputs are produced by earlier slices
