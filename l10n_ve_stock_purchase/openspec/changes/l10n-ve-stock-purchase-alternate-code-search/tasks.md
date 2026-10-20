## 1. Port the fix from the client staging hotfix

- [x] 1.1 Add `models/product_product.py` extending `product.product.name_search` to also match `alternate_code`, appended after `super()`, respecting `domain`/`limit`, excluding duplicate ids, and no-op on negative operators. Verified by reading the ticket 14833 section 5 code and porting it unchanged.
- [x] 1.2 Add `models/purchase_order_line.py` with a read-only `alternate_code` related field (`product_id.alternate_code`). Verified by `python3 -c "import ast; ast.parse(...)"` on the file.
- [x] 1.3 Add `models/__init__.py` and the package-level `__init__.py` importing `models`. Verified by `python3 -c "import ast; ast.parse(...)"` on both files.
- [x] 1.4 Add `views/purchase_order_views.xml` inheriting `purchase.purchase_order_form`, inserting an optional read-only `alternate_code` column after `product_id` in the order line list. Verified by `python3 -c "import xml.etree.ElementTree as ET; ET.parse(...)"`.

## 2. Manifest and translations

- [x] 2.1 Add `l10n_ve_stock` to `depends` (source of `product.template.alternate_code`) and add `views/purchase_order_views.xml` to `data` in `__manifest__.py`. Verified by `python3 -c "eval(open('__manifest__.py').read())"`.
- [x] 2.2 Bump the manifest `version` from the non-conforming `1.1` to `19.0.1.2.0`, matching the repo's `19.0.x.y.z` scheme. Verified by reading the updated manifest.
- [x] 2.3 Add `i18n/es_VE.po` translating the new field's `field_description` ("Alternate Code" → "Código Alterno") and `help` string. Verified with `msgfmt --check -o /dev/null i18n/es_VE.po`.

## 3. Verification

- [ ] 3.1 Update the module in a real Odoo 19 environment (`odoo -u l10n_ve_stock_purchase -d <db> --stop-after-init` or `./odoo update -d <db> -m l10n_ve_stock_purchase`) and confirm it installs/updates without errors.
- [ ] 3.2 In Purchase > Quotations > New, type a product's `alternate_code` (full and partial) in a line and confirm it resolves the expected product; confirm `default_code` and name search still work unchanged; confirm a non-matching text returns no results.
- [ ] 3.3 Confirm the "Código Alterno" column appears on the purchase order line list with the correct value, is read-only, and can be hidden from the optional columns picker.
- [ ] 3.4 Once deployed, uninstall/remove the temporary `maxcam_purchase_alternate_code` hotfix module from the client's staging environment to avoid a duplicate column (tracked in ticket 14833, not part of this PR).
