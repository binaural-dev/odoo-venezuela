# Delta — `l10n_ve_stock_account`

> **Tarea**: 80614

## ADDED Requirements

### Requirement: A Dispatch Guide Reserves A Control Number Per Sheet

When a transfer meets the existing `dispatch_guide_controls` condition (the
same one that governs `guide_number`), validating it (`_action_done`) MUST
reserve one control number per printed sheet the guide occupies, taken from
a company-scoped `ir.sequence` (`code="stock.picking.control.number"`).

A sheet holds at most `res.company.dispatch_guide_control_number_max_lines`
move lines (default 15). The sheet count MUST be
`ceil(len(move_line_ids) / max_lines)`, with a floor of 1 — a transfer with
no lines still reserves one control number.

A picking that already has control numbers MUST NOT be reassigned new ones.

#### Scenario: A short guide reserves one control number
- GIVEN a dispatch guide with fewer lines than the configured maximum
- WHEN it is validated
- THEN it has exactly one `stock.picking.control.number.line`

#### Scenario: A guide with no lines still reserves one
- GIVEN a dispatch guide with zero move lines
- WHEN it is validated
- THEN it has exactly one control number

#### Scenario: A guide over the maximum reserves an extra sheet
- GIVEN a dispatch guide with one more line than the configured maximum
- WHEN it is validated
- THEN it has two control numbers

#### Scenario: An exact multiple of the maximum reserves no extra sheet
- GIVEN a dispatch guide with exactly twice the configured maximum
- WHEN it is validated
- THEN it has exactly two control numbers

#### Scenario: Re-validating does not reserve new numbers
- GIVEN a dispatch guide that already has control numbers
- WHEN `_assign_control_numbers` runs again
- THEN its control numbers are unchanged

### Requirement: The Maximum Lines Per Sheet Is Company-Scoped

`res.company.dispatch_guide_control_number_max_lines` MUST default to 15 and
MUST be configurable independently per company, through
`res.config.settings`.

#### Scenario: Two companies use different maximums
- GIVEN two companies with a different configured maximum
- WHEN each validates a dispatch guide with the same number of lines
- THEN they may reserve a different number of sheets for it

### Requirement: The Control Number Sequence Is Isolated Per Company

The `ir.sequence` used to reserve control numbers MUST be scoped by
`company_id`, created on first use (search-or-create), mirroring
`get_sequence_guide_num`.

#### Scenario: Two companies never share a sequence
- GIVEN two companies that each validate a dispatch guide
- THEN each company's control numbers come from its own `ir.sequence` record

## Notes

- The control number is recorded for traceability only. It is not printed
  by Odoo — it is already pre-printed on the physical stationery by an
  authorized printer.
- This does not replace `account.move.correlative` (`l10n_ve_invoice`) or
  `control_number_tfhka` (`l10n_ve_invoice_digital`); it is a third, valid
  method of satisfying the same SENIAT control-number requirement, for
  clients whose invoicing runs on pre-printed paper instead of a fiscal
  sequence or a digital provider.
