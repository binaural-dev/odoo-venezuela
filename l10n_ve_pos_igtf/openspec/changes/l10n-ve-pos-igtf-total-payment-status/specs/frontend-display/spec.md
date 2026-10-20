## ADDED Requirements

### Requirement: totalWithIgtfAmount getter returns full invoice total plus full IGTF

The system MUST expose a `totalWithIgtfAmount` getter on `PaymentScreenStatus`
that returns, formatted as currency, the FULL invoice total (local currency,
without IGTF) plus 3% of that SAME full total — a fixed reference value that
does NOT depend on how much of the invoice has actually been entered across
payment lines so far. It MUST be derived from a dedicated order-model getter
(`get_total_with_igtf()` = `get_total_without_igtf() + compute_igtf_amount(get_total_without_igtf())`)
and MUST NOT use the incremental `igtf_amount` accumulated by `update_igtf()`
(that value is partial/proportional to the base already covered by
`apply_igtf` payment lines, and changes as the cashier types different
amounts — not suitable for this row). It also MUST NOT redefine or wrap
`get_total_with_tax()` / `get_foreign_total_with_tax()`, which stay as the
pure invoice-total conversion shared with `l10n_ve_pos` (native subtitle,
remaining panel, receipt, ticket, sale summary, backend
`foreign_amount_total`).

#### Scenario: Order with IGTF

- GIVEN an order with invoice total 100 (IGTF percentage 3%)
- WHEN the payment status renders
- THEN `totalWithIgtfAmount` shows the formatted value 103.00
- AND the native foreign subtitle under the total still shows the pure
  invoice total (unaffected)

#### Scenario: Partial amount typed in a payment line

- GIVEN an order with invoice total 100 (IGTF percentage 3%) and an
  `apply_igtf` payment line with only 10 entered so far (incremental
  `igtf_amount` = 0.30)
- WHEN the payment status renders
- THEN `totalWithIgtfAmount` still shows 103.00 (unaffected by the partial
  amount), while the BI IGTF / IGTF / Foreign IGTF breakdown above it keeps
  showing the incremental values tied to what has been entered

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
