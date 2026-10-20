# Spec delta: pos-odoo19-session-accounting

## ADDED Requirements

### Requirement: Combine cash receivable lines on the session closing move carry foreign amounts

`set_foreign_amount_in_line` SHALL write `foreign_debit`/`foreign_credit`
and `not_foreign_recalculate = True` on any `account.move.line` whose
`debit` or `credit` matches the payment method's accumulated `amount`,
regardless of whether a non-`asset_receivable` counterpart line exists in
the same `account.move`.

Session-closing moves only ever contain `asset_receivable` lines (the
combine cash payment method's own cash/bank account line is booked on a
separate bank-statement move), so a matched line with no counterpart
SHALL still receive its foreign write — the counterpart sync is an
additional step, not a precondition for writing the matched line itself.

#### Scenario: Combine cash receivable line with no counterpart in the same move

- **GIVEN** a POS session closed with one "combine" (non-split) cash
  payment method (`is_cash_count = True`, `is_foreign_currency = True`),
  paid with an amount whose foreign conversion does not round to zero
- **WHEN** the session's own closing move is created and its
  `combine_cash_receivable_lines` entry for that payment method contains
  only `asset_receivable` lines
- **THEN** that receivable line's `foreign_debit` (or `foreign_credit`)
  equals the payment method's accumulated `foreign_amount`, and
  `not_foreign_recalculate` is `True`

#### Scenario: Combine cash statement line with a counterpart (unchanged behavior)

- **GIVEN** the same combine cash payment method's bank-statement move,
  which contains both the `asset_receivable` line and the cash/bank
  account line
- **WHEN** `set_foreign_amount_in_line` runs on the receivable line
- **THEN** both the receivable line and its cash/bank counterpart end up
  with the matching `foreign_debit`/`foreign_credit`, exactly as before
  this fix

#### Scenario: Tiny amount legitimately rounds to zero

- **GIVEN** a payment method line whose domestic `debit`/`credit` is a
  fraction of a currency unit small enough that its foreign conversion
  rounds to `0.00` at the session's exchange rate
- **WHEN** `set_foreign_amount_in_line` runs
- **THEN** `foreign_debit`/`foreign_credit` are `0.00` and this is NOT
  treated as a defect — it is not distinguishable from the bug case by
  value alone, only by whether the underlying converted amount truly
  rounds to zero
