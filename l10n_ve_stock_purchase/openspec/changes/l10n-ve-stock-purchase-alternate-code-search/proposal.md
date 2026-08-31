## Why

Helpdesk ticket 14833: typing a product's `alternate_code` (Código Alterno) into a purchase order line does not resolve the product, because `product.product`'s core `name_search` only matches `default_code`, `name`, and `barcode`. A hotfix module (`maxcam_purchase_alternate_code`) already proves the fix works on a client staging environment, but it lives unversioned there and is lost on every rebuild. This change ports that verified fix into the shared product (`l10n_ve_stock_purchase`, repo `odoo-venezuela`) so it survives rebuilds and reaches every client, not just the one that reported it.

## What Changes

- Extend `product.product.name_search` to also match `alternate_code` (partial, case-insensitive), appended after the core `super()` results so the existing relevance order (`default_code` exact, then `barcode`, then partials) is preserved, with no duplicate ids and no behavior change for negative-operator domains.
- Add a read-only related field `purchase.order.line.alternate_code` (mirrors `product_id.alternate_code`, not stored).
- Add an optional, translated "Código Alterno" column to the purchase order line list view, positioned after "Product".
- Add `l10n_ve_stock` as a manifest dependency (source of `product.template.alternate_code`) and register the new view in `data`.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `l10n_ve_stock_purchase`: adds requirements for resolving products by `alternate_code` in `name_search` and for displaying that code as an optional column on purchase order lines. The module's dependency surface also grows from `purchase_stock`-only to include `l10n_ve_stock`.

## Impact

- **Module**: `l10n_ve_stock_purchase` (repo `odoo-venezuela`, base branch `19.0`).
- **New files**: `models/__init__.py`, `models/product_product.py`, `models/purchase_order_line.py`, `views/purchase_order_views.xml`, `i18n/es_VE.po`.
- **Manifest**: `depends` gains `l10n_ve_stock`; `data` gains `views/purchase_order_views.xml`; version bumped `1.1` → `19.0.1.2.0` (repo's `19.0.x.y.z` scheme; the previous `1.1` did not follow it).
- **No security/ACL changes** beyond the module's existing `security/ir.model.access.csv` (untouched).
- **Source ticket**: Helpdesk 14833. Once this ships, the temporary `maxcam_purchase_alternate_code` hotfix module on the client's staging environment must be uninstalled/removed to avoid a duplicate column.
