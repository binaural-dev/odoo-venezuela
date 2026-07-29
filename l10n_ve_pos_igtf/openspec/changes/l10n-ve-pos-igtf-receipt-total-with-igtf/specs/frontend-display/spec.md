## ADDED Requirements

### Requirement: Receipt screen shows the amount actually paid, IGTF included

The "Payment Successful" box of `point_of_sale.ReceiptScreen` MUST show the
total the customer actually paid — invoice total plus the IGTF surcharge that
was actually generated — in both the local and the foreign currency.

The surcharge used MUST be the order's real `igtf_amount` (what
`update_igtf()` accumulated over the base covered by `apply_igtf` payment
lines), NOT the fixed 3%-of-the-full-invoice reference value exposed by
`get_total_with_igtf()` for the payment status panel. At this point the order
is already validated, so the charged amount is known.

It MUST be derived from dedicated order-model getters
(`get_total_paid_with_igtf()` = `get_total_without_igtf() + igtf_amount`;
`get_foreign_total_paid_with_igtf()` = `get_foreign_total_with_tax() +
foreign_igtf_amount`, rounded with `roundForeignMoney`), mirroring the
backend's `pos.order::_get_total_with_igtf()`. It MUST NOT redefine or wrap
`get_total_with_tax()` / `get_foreign_total_with_tax()`, which stay the pure
invoice-total conversion shared with `l10n_ve_pos`.

#### Scenario: Invoice partially covered by an IGTF payment method

- GIVEN an invoiced order of 12.806,40 Bs / $ 17,37 (IGTF percentage 3%)
- AND a payment line of 7.372,30 Bs with an `apply_igtf` method, which
  generates 221,17 Bs / $ 0,30 of IGTF
- AND a second payment line of 5.655,27 Bs without IGTF
- WHEN the payment is validated and the receipt screen renders
- THEN the success box shows 13.027,57 Bs and $ 17,67
- AND the foreign amount equals the sum of the foreign parts shown elsewhere
  ($ 17,37 + $ 0,30)

#### Scenario: Order without IGTF

- GIVEN an order with no `apply_igtf` payment line, or a non-invoiced order
  (`update_igtf()` leaves `igtf_amount` at 0)
- WHEN the receipt screen renders
- THEN the local amount is the native `orderAmountPlusTip` (via `super()`) and
  the foreign amount is `get_foreign_total_with_tax()`, both unchanged

#### Scenario: Order with a tip

- GIVEN an order with IGTF and a tip line
- WHEN the receipt screen renders
- THEN the native "amount + tip" string layout is preserved, with the IGTF
  added to the non-tip part only

### Requirement: Receipt screen shows the IGTF surcharge breakdown

The success box MUST show, below the total and only when the order's
`igtf_amount` is non-zero, a smaller row with the IGTF surcharge in both
currencies, so the cashier can see why the confirmed amount differs from the
invoice total.

#### Scenario: Order with IGTF

- GIVEN an order whose `igtf_amount` is 221,17 Bs / $ 0,30
- WHEN the receipt screen renders
- THEN a row reading "IGTF: 221,17 Bs.F / $ 0,30" is shown under the total

#### Scenario: Order without IGTF

- GIVEN an order whose `igtf_amount` is 0
- WHEN the receipt screen renders
- THEN no IGTF row is shown

### Requirement: The foreign total override is located by expression, not position

The XML inheritance MUST select the foreign total added by `l10n_ve_pos` by
its `t-out` expression (`contains(@t-out, 'get_foreign_total_with_tax')`)
rather than by sibling position, because the `<span>` that `l10n_ve_pos`
inserts carries no class or id and its index depends on that module's own
insertion point.

#### Scenario: Inheritance chain applied

- GIVEN `point_of_sale.ReceiptScreen` extended by `l10n_ve_pos` and then by
  `l10n_ve_pos_igtf`
- WHEN the templates are merged
- THEN both xpaths match exactly one node
- AND the native "Edit Payment" badge remains a sibling of the amounts
