## ADDED Requirements

### Requirement: Option to report fiscal-machine documents in the sale book
The accounting reports wizard (`wizard.accounting.reports`) SHALL offer a
`with_fiscal_machine` option that reports ONLY documents issued by a fiscal
machine (those with `mf_serial`, `mf_reportz` and `mf_invoice_number` and no
control number), grouped as a daily sales summary ("Resumen Diario de Ventas")
per Z report.

#### Scenario: Fiscal-only sale book groups by Z report
- **WHEN** the user enables `with_fiscal_machine` and generates the sale book
  for a range containing fiscal-machine POS invoices
- **THEN** ordinary final-consumer sales are collapsed into a daily summary line
  per Z report, while taxpayer (RIF "J" / special / non-ordinary) invoices and
  credit notes appear as individual lines
- **AND** the sheet shows the columns "N° Máquina Fiscal", "Reporte Z" and
  "Serial de Máquina"

### Requirement: Option to include all issued documents
The wizard SHALL offer an `all_documents` option that includes BOTH free-form
documents (with control number) AND fiscal-machine documents (without control
number) in the same book, line by line.

#### Scenario: All documents combines both sources
- **WHEN** the user enables `all_documents` and generates the sale book
- **THEN** the book lists free-form invoices (with their control number) and
  fiscal-machine invoices (control number shown as "--", with the fiscal-machine
  columns filled), ordered by document date

### Requirement: Options are mutually exclusive and off by default
`with_fiscal_machine` and `all_documents` MUST be mutually exclusive in the form
and both default to False.

#### Scenario: Default behavior unchanged
- **WHEN** neither option is enabled
- **THEN** the sale/purchase book is generated exactly as before, including only
  moves whose `correlative` is set
