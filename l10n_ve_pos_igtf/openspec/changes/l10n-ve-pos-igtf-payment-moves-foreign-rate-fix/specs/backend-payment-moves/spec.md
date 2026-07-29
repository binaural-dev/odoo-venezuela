## MODIFIED Requirements

### Requirement: _create_payment_moves preserves the payment's foreign rate

`_create_payment_moves` MUST persist the foreign-currency rate that was
actually in effect at payment time (`payment.foreign_rate`) on the created
`account.move`, and MUST mark it as manually set so that downstream
automatic rate recomputation (`account.move.create()` →
`_compute_rate()` in `l10n_ve_accountant`) does not overwrite it with the
rate computed at move-creation time.

#### Scenario: IGTF payment move preserves its own rate

- GIVEN a POS payment with `include_igtf = true` and `foreign_rate = 250`
- WHEN `_create_payment_moves` creates the payment's `account.move`
- THEN the move has `foreign_rate = 250`, `foreign_inverse_rate = 250`, and
  `manually_set_rate = True`
- AND a later `write()` on the move (e.g. reconciliation) does not trigger
  `_compute_rate_for_documents` to replace that rate with the current day's
  rate
