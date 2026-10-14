# Spec delta: pos-odoo19-session-accounting

## ADDED Requirements

### Requirement: The closing cash statement balances in the alternate currency at the sale rate

`set_foreign_amount_in_line` SHALL lock the cash leg of a bank-statement move (`move_id.statement_line_id` set) when it matches its receivable line: it writes the mirrored `foreign_debit`/`foreign_credit` and sets `not_foreign_recalculate = True`, so the cash leg is not recomputed at the rate of the move date.
On any other move it SHALL NOT write or lock any line other than the matched one.

#### Scenario: BCV rate changes between the sale and the closing

- **GIVEN** a POS order paid in cash at rate A
- **AND** the rate of the closing day is B, different from A
- **WHEN** the session is closed and the cash statement is booked
- **THEN** the statement's receivable leg and cash leg carry the same
  alternate amount (the sale-time `foreign_amount`), both with
  `not_foreign_recalculate = True`, and the statement's foreign debit equals
  its foreign credit

#### Scenario: Session closing move with sales lines

- **GIVEN** the session's own closing move, whose non-receivable lines are
  sales or tax lines
- **WHEN** `set_foreign_amount_in_line` runs on its receivable line
- **THEN** only the receivable line is written and locked; the sales and tax
  lines keep `not_foreign_recalculate = False`
