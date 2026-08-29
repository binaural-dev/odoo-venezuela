## Why

The `packaging_picking` report (embalaje/etiquetas de bulto) iterates with `range(1, picking.package_qty + 1)`. When `package_qty` is 0 (an unset field on the picking) this produces `range(1, 1)`, an empty range - the parent's `t-foreach` never invokes `packaging_picking_item` for that picking, so the report prints zero labels with no visible error. A "treat it as 1 package" fallback already existed inside `packaging_picking_item`, but it was unreachable: the parent had already discarded the iteration before ever calling that template.

## What Changes

- Move the "package_qty == 0 → treat as 1" guard from inside `packaging_picking_item` (where it never ran) to the parent's `range()` computation: `range(1, (picking.package_qty if picking.package_qty and picking.package_qty > 0 else 1) + 1)`. This also covers `None` and negative values, not just exactly `0`.
- The `t-if`/`t-else` block on `package_qty == 0` inside `packaging_picking_item` is kept as-is - it still has a real, visible use: it makes the "Package X / Y" label show `Y=1` instead of `Y=0` when `package_qty` is 0.
- Remove dead commented-out code (`operation_employees`/`pick_employee`/`out_employee`) in `packaging_picking_item` that was unused anywhere.

## Capabilities

### Modified Capabilities
- `l10n_ve_stock`: adds a requirement for the packaging/label report's behavior when `package_qty` is 0, unset, or negative (not previously documented in this capability's spec).

## Impact

- **Module**: `l10n_ve_stock` (file: `report/packaging_picking_template.xml`).
- **Report**: `l10n_ve_stock.action_packaging_picking` ("Packaging tags"), model `stock.picking`.
- **No Python/model changes** - template-only fix.
- **Manifest version bump**: `l10n_ve_stock` version bumped alongside this fix (patch-level), per repo convention of bumping the module version whenever its code changes.
