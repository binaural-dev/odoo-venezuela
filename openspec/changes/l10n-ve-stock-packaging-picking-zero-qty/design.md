## Context

`packaging_picking` is a plain QWeb report template (no Python model involved): a parent template (`packaging_picking`) iterates `range(1, picking.package_qty + 1)` and calls a child template (`packaging_picking_item`) once per resulting page. See proposal.md for the bug this fixes.

## Goals / Non-Goals

**Goals:**
- Make the report print at least one label for a picking with `package_qty` unset/0/negative, without touching any Python model or stored field.

**Non-Goals:**
- Not changing what `package_qty` means or how/when it gets set elsewhere in the codebase - this is purely about how the report reacts to it being 0.

## Decisions

- **Fix the guard at the parent's `range()` call, not inside the child template.** The child already had a `package_qty == 0` fallback, but it's structurally unreachable there: the parent's `t-foreach` decides how many times (if any) to call the child, so a 0-or-negative value has to be normalized before that `range()` call, not after.
- **Keep the existing `t-if`/`t-else` inside `packaging_picking_item`**, rather than deleting it as now-fully-dead code: it still drives the "Package X / Y" label's denominator, so removing it would make the label show `Y=0` again for this same case.

## Risks / Trade-offs

- [None identified beyond the fix itself] → This is a narrowly-scoped template change with no Python/model surface; the existing dead-code cleanup (unused comments) carries no behavioral risk.

## Migration Plan

Template-only change to an existing report (`l10n_ve_stock.action_packaging_picking`). No data migration. Module version bump on `l10n_ve_stock` triggers the view reload on the next module update.
