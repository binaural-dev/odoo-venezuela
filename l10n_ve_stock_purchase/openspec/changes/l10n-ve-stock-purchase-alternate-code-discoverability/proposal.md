## Why

The module already resolves and displays a product's `alternate_code` (Código Alterno) in the purchase order line — shipped by `l10n-ve-stock-purchase-alternate-code-search` (ticket 14833). But nothing about the module's `name`, `summary`, `description`, or its entry in the repo-root `README.md` mentioned that capability; both stayed generic ("gestión de inventario/compras en Venezuela"). Anyone searching Apps or the README for "código alterno" would not find this module.

This is not hypothetical: the same ticket's Odoo.sh diagnostic surfaced a loose, unversioned module (`maxcam_purchase_alternate_code`) mounted directly in a client build's editor, duplicating this exact functionality — created because nobody could tell the capability already existed here.

## What Changes

- Update the manifest `summary`/`description` of `l10n_ve_stock_purchase` to explicitly mention the Código Alterno search and column.
- Update the module's entry in the repo-root `README.md` module summary to mention the same.
- No functional/behavioral change; no data, model, or view changes.

## Capabilities

### New Capabilities
- `l10n_ve_stock_purchase`: adds a discoverability requirement — the module's metadata (manifest `summary`/`description`) and its `README.md` entry must state that it handles Código Alterno, so the capability added by `l10n-ve-stock-purchase-alternate-code-search` is findable without reading the code.

### Modified Capabilities
(none)

## Impact

- **Module**: `l10n_ve_stock_purchase` (repo `odoo-venezuela`, base branch `maintenance-19.0`).
- **Changed files**: `__manifest__.py` (`summary`, `description`, version bump), repo-root `README.md`.
- **No security/ACL/behavior changes.**
- **Source ticket**: Helpdesk 14833 (same ticket as the original search fix, follow-up finding).
