## 1. Fix
- [x] 1.1 Move the `package_qty` zero/negative/unset guard to the parent `packaging_picking` template's `range()` call. Verified by reading the full diff of commit `0fed35d1d`.
- [x] 1.2 Keep the existing `t-if`/`t-else` inside `packaging_picking_item` (drives the "Package X / Y" label denominator) - confirmed it is not dead code before touching anything.
- [x] 1.3 Remove unused commented-out code (`operation_employees`/`pick_employee`/`out_employee`) in `packaging_picking_item`.
- [x] 1.4 Bump `l10n_ve_stock`'s manifest version (`19.0.1.0.7` → `19.0.1.0.8`).

## 2. Verification
- [ ] 2.1 After merge, print "Packaging tags" for a real picking with `package_qty` unset and confirm it prints one label ("Package 1 / 1") instead of an empty report.
