# Foreign Base Line Currency Resolution Specification

> **Organization**: binaural-dev
> **Author**: Binaural Claude

## Purpose

Defines how `_prepare_foreign_base_line_for_taxes_computation` resolves the
`currency_id` of a foreign-currency base line, so it never ends up empty.

## Requirements

### Requirement: Explicit Caller Currency Wins

When the caller passes an explicit `currency_id` kwarg, the resulting base
line MUST use that currency, not `company.foreign_currency_id`.

#### Scenario: Sale order line passes its own order currency
- GIVEN a sale order line calling with `currency_id=EUR`
- AND the company's `foreign_currency_id` is USD
- THEN the base line's `currency_id` is EUR

### Requirement: Currency Is Never Empty

When neither the caller nor the record provide a `currency_id`, and the
company has no `foreign_currency_id` configured, the base line MUST fall
back to `company.currency_id` — never an empty `res.currency` recordset.

#### Scenario: Company without bimonetary setup
- GIVEN a company with `foreign_currency_id` unset
- AND no explicit `currency_id` passed
- THEN the base line's `currency_id` is `company.currency_id`
- AND it is truthy (not an empty recordset)
