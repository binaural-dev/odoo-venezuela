# POS Odoo 19 Session Accounting Specification

## Purpose

Define how `l10n_ve_pos` migrates session-closing accounting overrides to Odoo 19 dict/record structures without losing foreign-currency amounts.

## Requirements

### Requirement: Inventory and map accounting overrides

The migration plan MUST list every override of `_accumulate_amounts`, `_create_split_account_payment`, `_create_bank_payment_moves`, `_create_cash_statement_lines_and_cash_move_lines`, `_create_invoice_receivable_lines`, `_create_account_move`, `_update_amounts`, `set_foreign_amount_in_line`, and `_create_payment_moves` in `l10n_ve_pos`, and map each to the Odoo 19 equivalent.

#### Scenario: Accounting override inventory is complete

- GIVEN `src/odoo-venezuela/l10n_ve_pos/models/pos_session.py`
- WHEN the reviewer compares it with the mapping table
- THEN every accounting override has a source line reference and an Odoo 19 target

#### Scenario: Payment move override is included

- GIVEN `pos_payment.py`
- WHEN the reviewer checks the mapping table
- THEN `_create_payment_moves` and its foreign-field writes are listed

### Requirement: Model before/after data structures

The plan MUST include a comparison of the `data` dict keys produced by `_accumulate_amounts` and consumed by the other accounting methods in Odoo 17 versus Odoo 19.

#### Scenario: Key mapping is documented

- GIVEN the design document
- WHEN the reviewer inspects the accounting data-flow section
- THEN a table shows each Odoo 17 key, the Odoo 19 equivalent if renamed, and the custom `foreign_*` keys that remain

#### Scenario: Missing key is caught early

- GIVEN the before/after table
- WHEN a reviewer adds a new accounting slice
- THEN the table is used as a checklist to verify no required key is dropped

### Requirement: Preserve foreign amount accumulation

The plan MUST keep the aggregation of `foreign_amount` for split/combine cash, bank, and invoice receivables inside the migrated `_accumulate_amounts`.

#### Scenario: Split cash foreign amount accumulates

- GIVEN a split cash payment in foreign currency
- WHEN `_accumulate_amounts` runs
- THEN the resulting dict entry contains both `amount`/`amount_converted` and `foreign_amount`

#### Scenario: Invoiced order foreign amount accumulates

- GIVEN an invoiced order with a bank payment
- WHEN the amounts are accumulated
- THEN the invoice receivables entry includes `foreign_amount`

### Requirement: Preserve payment-move foreign fields

The plan MUST preserve the writes of `foreign_rate`, `foreign_inverse_rate`, `manually_set_rate`, `not_foreign_recalculate`, `foreign_debit`, and `foreign_credit` on generated `account.move` and `account.move.line` records.

#### Scenario: Split account payment sets foreign fields

- GIVEN a split bank payment with foreign amount
- WHEN `_create_split_account_payment` creates the account payment
- THEN the payment move has `foreign_rate` and `foreign_inverse_rate`, and its lines have `not_foreign_recalculate`, `foreign_debit`, and `foreign_credit`

#### Scenario: Cash move lines set foreign fields

- GIVEN a cash payment with foreign amount
- WHEN `_create_cash_statement_lines_and_cash_move_lines` runs
- THEN the corresponding move lines have `foreign_debit` or `foreign_credit`

### Requirement: Define high-risk accounting verification scenarios

The plan MUST specify tests for multi-currency session closing, split payments, combined payments, refunds, and invoiced orders.

#### Scenario: Multi-currency session close is balanced

- GIVEN a closed POS session with VES and USD payments
- WHEN the session accounting entries are created
- THEN the session move balances and foreign-currency amounts match the payments

#### Scenario: Refund session closes correctly

- GIVEN a refund order paid in foreign currency
- WHEN the session is closed
- THEN no unreconciled foreign-currency difference appears
