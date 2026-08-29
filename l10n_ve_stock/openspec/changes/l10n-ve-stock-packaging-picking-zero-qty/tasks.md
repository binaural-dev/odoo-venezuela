## 1. Fix
- [x] 1.1 Move the `package_qty` zero/negative/unset guard to the parent `packaging_picking` template's `range()` call. Verified by reading the full diff of commit `0fed35d1d`.
- [x] 1.2 Keep the existing `t-if`/`t-else` inside `packaging_picking_item` (drives the "Package X / Y" label denominator) - confirmed it is not dead code before touching anything.
- [x] 1.3 Remove unused commented-out code (`operation_employees`/`pick_employee`/`out_employee`) in `packaging_picking_item`.
- [x] 1.4 Bump `l10n_ve_stock`'s manifest version (`19.0.1.0.5` → `19.0.1.0.6`, on the `maintenance-19.0` baseline).

## 2. Verification
- [ ] 2.1 After merge, print "Packaging tags" for a real picking with `package_qty` unset and confirm it prints one label ("Package 1 / 1") instead of an empty report.

## 3. Recipient name guard (outgoing-only, `display_name`)
- [x] 3.1 Restrict the recipient name line to `picking.picking_type_id.code == 'outgoing'` and `picking.partner_id` set.
- [x] 3.2 Switch from `partner_id.name` to `partner_id.display_name`, per explicit client request.
- [x] 3.3 Wrap with `(... or '')[:80]` as an extra safety layer against an empty `display_name`.
- [x] 3.4 Bump `l10n_ve_stock`'s manifest version (`19.0.1.0.6` → `19.0.1.0.7`).

## 4. Verification
- [ ] 4.1 After merge, print "Packaging tags" for an outgoing picking with `partner_id` set and confirm the recipient's `display_name` prints correctly.
- [ ] 4.2 After merge, print "Packaging tags" for an outgoing picking with `partner_id` empty and confirm the report no longer raises `TypeError` and simply omits the recipient name line.
- [ ] 4.3 After merge, print "Packaging tags" for a non-outgoing picking (e.g. internal transfer) and confirm the recipient name line does not print.
