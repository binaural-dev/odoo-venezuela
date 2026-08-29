## Context

`product.product` already overrides `name_search` in Odoo core (prioritizes exact `default_code`, then `barcode`, then partial matches) and overrides `_search_display_name`. In Odoo 19 the many2one autocomplete in the web client calls `web_name_search` (`addons/web/models/models.py`), which delegates to `self.name_search(name, domain, operator, limit)` — so extending `name_search` on `product.product` covers the purchase order line dropdown (and any other many2one using the same path) without touching the view widget or a separate `_search_display_name` override. See proposal.md for the motivating bug.

Note the Odoo 19 signature change from earlier versions: the second positional argument is `domain` (not `args`). An override copied from a 17.0/18.0 base with `args=None` breaks the `super()` call.

## Goals / Non-Goals

**Goals:**
- Make `alternate_code` a first-class match key in `product.product.name_search`, without discarding or reordering what `super()` already returns.
- Surface the resolved code back on the purchase order line as a read-only reference, so buyers can visually confirm which code matched.

**Non-Goals:**
- Not changing `product.template.alternate_code` itself (already defined in `l10n_ve_stock`) or its constraints/uniqueness.
- Not touching `_search_display_name` or the core `name_search` relevance order for `default_code`/`barcode`/`name` — only appending.
- Not extending this behavior to sales order lines or other many2one pickers in this change; scope is purchase order lines only, per the ticket.

## Decisions

- **Extend `name_search`, don't replace it.** Alternatives considered: overriding `_search_display_name` instead (rejected — that path is for computing display names, not full-text candidate search, and duplicating the core `name_search` logic there would be more invasive and easier to desync from core updates); overriding at the view/widget level with a custom `search_default` domain (rejected — doesn't cover other callers of `name_search`, e.g. API/XML-RPC clients).
- **Append `alternate_code` matches after `super()`'s results, excluding ids already returned.** This preserves the existing relevance order (exact `default_code` first) and avoids showing the same product twice when it matches on both criteria.
- **Respect the caller's `domain` and remaining `limit`.** The alternate-code search reuses the caller's `domain` (AND-ed with the `alternate_code` condition) and only asks for `limit - len(results)` additional records, so callers that pass a restrictive domain or a small limit still get correct, bounded results.
- **No-op on negative operators (`not ilike`, `not in`, etc.).** `Domain.NEGATIVE_OPERATORS` is used as the guard; negating a "code contains X" condition across two fields via simple concatenation would not produce a correct "does not match" set, so those cases fall through to `super()`'s behavior unchanged.
- **`purchase.order.line.alternate_code` as `related`, not stored/computed.** It is a pure read-only mirror of `product_id.alternate_code` for display purposes; there is no independent value to store or business logic to compute, so `related=` is the simplest, always-in-sync choice.
- **New view field is `optional="show"`, `readonly="1"`.** Visible by default but a user can hide it from the optional-columns picker; read-only because the source of truth is the product form, not the purchase line.
- **`l10n_ve_stock_purchase` gains `l10n_ve_stock` as a dependency, not `l10n_ve_stock`(the product module) itself absorbing purchase view logic.** `alternate_code` is defined in `l10n_ve_stock` on `product.template`, but that module intentionally does not depend on `purchase` — it is inventory-scoped. `l10n_ve_stock_purchase` is the existing inventory/purchase bridge module, so it is the correct place for a `purchase.order.line` view inheritance and a `product.product` override that only matters in a purchasing context.

## Risks / Trade-offs

- [Extra DB query per `name_search` call when the caller's typed text does not already match via `super()`] → Bounded by `remaining_limit` and short-circuited entirely (`return results` before querying) whenever `super()` already fills the requested `limit`, or when the search term is empty, or on negative operators.
- [Duplicate products if `search_fetch` returns an id also present in `results`] → Explicitly excluded via `Domain("id", "not in", [...])` before calling `search_fetch`.
- [None beyond the two above] → No `sudo()` is used on the alternate-code matches: `search_fetch` already runs as the calling user and enforces `ir.rule`, and `alternate_code` carries no `groups=` restriction, so reading `display_name` off the resulting recordset needs no elevated privileges. (An earlier draft of this change added `.sudo()` here, copied from the similar pattern in `integra-addons/binaural_alternate_product_name`; removed after confirming it was a no-op that would silently mask any future field-level restriction on the display_name compute chain.)

## Migration Plan

No data migration. Adding the `alternate_code` related field and the view triggers a standard module update (`-u l10n_ve_stock_purchase`) picking up the new field/view/dependency. Rollback is a plain module downgrade/revert since no stored data or ACL changes are introduced. Once this ships, the temporary staging module `maxcam_purchase_alternate_code` must be uninstalled to avoid two "Código Alterno" columns on the same view.
