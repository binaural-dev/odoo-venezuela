# Foreign base line currency resolution: explicit kwarg + non-empty fallback

> **Organization**: binaural-dev
> **Author**: Binaural Claude
> **Ticket**: PENDIENTE (asignar antes de push/PR — bug preexistente, no
>   relacionado a la Tarea 80614, se resuelve por separado)
> **Status**: implemented

## Why

`_prepare_foreign_base_line_for_taxes_computation` had two related bugs:

1. `kwargs.get('currency_id')` was ignored: the dict literal that builds
   `base_line` set `'currency_id': currency` *after* `**kwargs` in the same
   literal, so whatever `currency_id` the caller explicitly passed (every
   real caller — `sale.order.line`, `purchase.order.line`) was silently
   discarded and replaced.
2. The replacement fell back to `self.env.company.foreign_currency_id`, with
   no further fallback. `foreign_currency_id` is an optional `Many2one`: on
   a company that doesn't use the bimonetary VES/USD setup, it returns an
   **empty** `res.currency` recordset — not `None` — which crashes
   downstream in `_round_base_lines_tax_details`'s `currency.round(...)`
   with `ValueError: Expected singleton: res.currency()` the moment a
   sale/purchase order computes its tax totals.

Found by reproducing it live in `giralda_test` (Odoo 19): a plain
`env['sale.order'].create(...)` + `action_confirm()` against a fresh
company with no `foreign_currency_id` configured crashed reliably. Confirmed
the same root cause on the purchase side
(`binaural_purchase/models/purchase_order.py`) by reproducing via a module
install that recomputes `_compute_tax_totals`.

This is shared VE localization code (`l10n_ve_accountant`) — it affects any
Binaural VE client, not only Giralda. It likely went undetected because real
production companies almost always have `foreign_currency_id` configured
(Venezuelan bimonetary accounting is close to universal there), so the
empty-currency edge case rarely triggers outside a fresh/test company.

## What Changes

`l10n_ve_accountant/models/account_tax.py`,
`_prepare_foreign_base_line_for_taxes_computation`:

```python
currency = (
    kwargs.get('currency_id')
    or load('foreign_currency_id', None)
    or self.env.company.foreign_currency_id
    or self.env.company.currency_id)
```

`kwargs['currency_id']` now wins first (as every real caller intends), and
`company.currency_id` is added as a final fallback so `currency` is never an
empty recordset.

## Impact

- **Capability**: `foreign-base-line-currency-resolution` (new).
- **Modules**: `l10n_ve_accountant` only.
- **Not part of Tarea 80614**: found while preloading test data for that
  task's browser verification, but this bug is unrelated to the dispatch
  guide feature — kept in its own commit/change so it can be triaged and
  merged independently.

## Risks

- None identified: the change only widens what already-passed values are
  respected and adds a fallback for a case that previously crashed outright
  — there is no prior "working" behavior for the empty-currency path to
  regress.

## Rollback

Revert the commit. Companies without `foreign_currency_id` configured go
back to crashing on tax-totals computation for sale/purchase orders.

## Success criteria

1. An explicit `currency_id` kwarg from the caller is respected, not
   overwritten by `company.foreign_currency_id`.
2. A company with no `foreign_currency_id` and no explicit `currency_id`
   resolves to `company.currency_id`, never an empty recordset.
3. `test_11_prepare_foreign_base_line_respects_explicit_currency_kwarg` and
   `test_12_prepare_foreign_base_line_falls_back_to_company_currency`
   (`tests/test_account_tax_foreign.py`) pass.
