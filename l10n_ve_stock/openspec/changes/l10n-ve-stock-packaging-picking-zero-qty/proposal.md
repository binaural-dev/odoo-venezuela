## Why

The `packaging_picking` report (embalaje/etiquetas de bulto) iterates with `range(1, picking.package_qty + 1)`. When `package_qty` is 0 (an unset field on the picking) this produces `range(1, 1)`, an empty range - the parent's `t-foreach` never invokes `packaging_picking_item` for that picking, so the report prints zero labels with no visible error. A "treat it as 1 package" fallback already existed inside `packaging_picking_item`, but it was unreachable: the parent had already discarded the iteration before ever calling that template.

## What Changes

- Move the "package_qty == 0 → treat as 1" guard from inside `packaging_picking_item` (where it never ran) to the parent's `range()` computation: `range(1, (picking.package_qty if picking.package_qty and picking.package_qty > 0 else 1) + 1)`. This also covers `None` and negative values, not just exactly `0`.
- The `t-if`/`t-else` block on `package_qty == 0` inside `packaging_picking_item` is kept as-is - it still has a real, visible use: it makes the "Package X / Y" label show `Y=1` instead of `Y=0` when `package_qty` is 0.
- Remove dead commented-out code (`operation_employees`/`pick_employee`/`out_employee`) in `packaging_picking_item` that was unused anywhere.

## Also in this change: recipient name shown only for outgoing pickings, using `display_name`

`packaging_picking_item` printed the partner's name (`picking.partner_id.name[:80]`) unconditionally, regardless of picking type, and without checking that `partner_id` is set. This caused a real `TypeError: 'bool' object is not subscriptable` (confirmed `RPC_ERROR` in staging logs) when printing a label for a picking with an empty `partner_id`. Fix:

- Only show the recipient name when `picking.picking_type_id.code == 'outgoing'` (the recipient name is only meaningful for outgoing deliveries) **and** `picking.partner_id` is set.
- Use `partner_id.display_name` instead of `partner_id.name`, per explicit client request.
- Guard against an empty `display_name` with `(picking.partner_id.display_name or '')[:80]` as an extra safety layer beyond the `t-if`.

## Capabilities

### Modified Capabilities
- `l10n_ve_stock`: adds a requirement for the packaging/label report's behavior when `package_qty` is 0, unset, or negative (not previously documented in this capability's spec).
- `l10n_ve_stock`: adds a requirement restricting the recipient name line to outgoing pickings with a set `partner_id`, and switching to `display_name`.

## Impact

- **Module**: `l10n_ve_stock` (file: `report/packaging_picking_template.xml`).
- **Report**: `l10n_ve_stock.action_packaging_picking` ("Packaging tags"), model `stock.picking`.
- **No Python/model changes** - template-only fix.
- **Manifest version bump**: `l10n_ve_stock` version bumped alongside this fix (patch-level), per repo convention of bumping the module version whenever its code changes.
