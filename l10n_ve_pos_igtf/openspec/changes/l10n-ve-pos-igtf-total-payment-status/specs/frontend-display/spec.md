## ADDED Requirements

### Requirement: totalWithIgtfAmount getter returns invoice total plus IGTF

The system MUST expose a `totalWithIgtfAmount` getter on `PaymentScreenStatus`
that returns, formatted as currency, the invoice total (local currency,
without IGTF) plus the computed IGTF surcharge. It MUST be derived from a
dedicated order-model getter (`get_total_with_igtf()`) and MUST NOT redefine
or wrap `get_total_with_tax()` / `get_foreign_total_with_tax()`, which stay as
the pure invoice-total conversion shared with `l10n_ve_pos` (native subtitle,
remaining panel, receipt, ticket, sale summary, backend
`foreign_amount_total`).

#### Scenario: Order with IGTF

- GIVEN an order with invoice total 100 and IGTF amount 3
- WHEN the payment status renders
- THEN `totalWithIgtfAmount` shows the formatted value 103.00
- AND the native foreign subtitle under the total still shows the pure
  invoice total (unaffected)

### Requirement: Payment status panel shows a combined total row

The payment status panel MUST show, only when `isIgtf` is true, a row labeled
"TOTAL a Pagar con IGTF:" below the existing BI IGTF / IGTF / Foreign IGTF
breakdown, visually separated by a top border, in a larger font than the
breakdown rows, with the amount right-aligned.

#### Scenario: IGTF payment line present

- GIVEN a payment line whose method has `apply_igtf` true
- WHEN the payment status panel renders
- THEN the BI IGTF / IGTF / Foreign IGTF breakdown is shown
- AND a separated "TOTAL a Pagar con IGTF:" row is shown below it with the
  combined amount

#### Scenario: No IGTF payment line

- GIVEN no payment line has `apply_igtf` true
- WHEN the payment status panel renders
- THEN neither the breakdown nor the "TOTAL a Pagar con IGTF:" row is shown
