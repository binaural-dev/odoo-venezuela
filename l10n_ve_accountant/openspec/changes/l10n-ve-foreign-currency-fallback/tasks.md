# Tasks — Foreign base line currency resolution

> **Ticket**: PENDIENTE (bug preexistente, separado de la Tarea 80614)

## Implementation

- [x] `_prepare_foreign_base_line_for_taxes_computation`: `kwargs.get('currency_id')` wins first.
- [x] Add `self.env.company.currency_id` as final fallback (never an empty recordset).

## Verification

- [x] `test_11_prepare_foreign_base_line_respects_explicit_currency_kwarg` (new).
- [x] `test_12_prepare_foreign_base_line_falls_back_to_company_currency` (new).
- [x] Reproduced live in `giralda_test`: sale order create+confirm against a company with no `foreign_currency_id` no longer crashes.
- [x] `l10n_ve_accountant` test suite (`l10n_ve_accountant_tax_foreign` tag): 12/12 pass, no regressions in the other 10 pre-existing tests.

## Pending

- [ ] Ticket ID before push/PR.

## OpenSpec

- [x] `proposal.md` + this file.
