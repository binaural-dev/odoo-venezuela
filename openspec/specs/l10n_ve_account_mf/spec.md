# l10n_ve_account_mf — Accounting / Invoicing Fiscal Machine Integration (Odoo 19)

## Purpose

Integrates TFHKA fiscal printers with Odoo Accounting (Facturación/Contabilidad) via Web Serial API. New module for Odoo 19 that replaces the Web Serial portion of the legacy `l10n_ve_iot_mf` **without any dependency on the `iot` module or the IoT Box stack**. Handles invoice/refund/debit-note printing from the `account.move` form view, fiscalizador (debug) tool, systray connection status, MF reports wizard (X, Z, date-range print, date-range reprint), company-level configuration (`mf_flag_21`, `invoice_print_type`), and persistence of fiscal metadata on invoices. Installable independently of the POS module; both can coexist (shared field names on `account.move` and `account.tax`).

## Requirements

### Requirement: Invoice Fiscal Printing from Form View
The system SHALL allow printing fiscal documents (invoice, credit note, debit note) directly from the `account.move` form view via Web Serial API.

#### Scenario: Print customer invoice
- **WHEN** the user clicks "Imprimir Factura (MF)" on a validated `out_invoice`
- **THEN** the system validates via `check_print_out_invoice()` (not printed before, posted, date is today, credit invoice without payments) and builds the payload (partner with `prefix_vat-vat`, lines with `fiscal_code` and line discount pre-applied, payments from the payments widget converted to VEF with `foreign_inverse_rate`)
- **AND** sends the command sequence via `TfhkaDriver.printInvoice`
- **AND** persists `mf_invoice_number`, `mf_serial`, `mf_reportz` on the invoice
- **AND** logs failures to the chatter via `log_mf_print_failure`

#### Scenario: Duplicate fiscal number warning
- **WHEN** persisting a fiscal number that already exists on another invoice
- **THEN** a warning is posted to the chatter and a sticky warning notification is returned (standard `display_notification`, no third-party wizard dependency)

#### Scenario: Credit note requires the affected invoice fiscal data
- **WHEN** printing an `out_refund`
- **THEN** the affected invoice block is built from `reversed_entry_id` (`mf_invoice_number`, `mf_serial`, `invoice_date` as DD/MM/YYYY) and the print is rejected if the original invoice has no fiscal number
- **AND** for credit notes originating from POS, real `pos.order` payments are used to preserve the per-method fiscal breakdown

#### Scenario: Debit note
- **WHEN** printing a debit note (journal flagged as debit, `is_debit_journal`)
- **THEN** the affected invoice block is built from `debit_origin_id` and the driver prints via `printDebitNote`

#### Scenario: Reprint
- **WHEN** the user clicks "Reimprimir (MF)" on a document with `mf_invoice_number`
- **THEN** `check_reprint()` returns the type and fiscal number and the driver reprints via `RF`/`RC` commands

#### Scenario: Date validation uses user timezone
- **WHEN** checking that the invoice date is not in the future
- **THEN** `fields.Date.context_today(self)` is used (respects user timezone)

### Requirement: MF Reports Wizard
The system SHALL provide a wizard accessible from the "Detalle de Ventas" menu for fiscal report operations.

#### Scenario: Print Report X
- **WHEN** the user clicks "Imprimir Reporte X" with the fiscal printer connected
- **THEN** the driver sends the I0X command

#### Scenario: Print Report Z with backend sync
- **WHEN** the user confirms "Imprimir Reporte Z" (explicit ConfirmationDialog)
- **THEN** the driver sends I0Z, reads S1, and calls `account.move.report_z()` to assign Z+1 to all pending invoices of that machine

#### Scenario: Print resume by date range (I2S)
- **WHEN** the user selects date_from/date_to and clicks "Impresion por rango de fecha"
- **THEN** dates are read from the form record, formatted to DDMMYY, and the `I2S<from><to>` command is sent with 30s timeout
- **AND** date_to >= date_from is validated

#### Scenario: Reprint invoices by date range (Rf)
- **WHEN** the user selects date_from/date_to and clicks "Reimpresion facturas por fecha"
- **THEN** the `Rf<from><to>` command is sent with 60s timeout (7-digit zero-padded payload, parity with the v17 implementation)
- **AND** date parsing handles multiple formats: YYYY-MM-DD, DD/MM/YYYY, Date and Luxon DateTime objects

### Requirement: Fiscalizador (Debug Tool)
The system SHALL provide a debug dialog accessible from the Developer Tools menu (bug icon) for technical diagnostics.

#### Scenario: Open fiscalizador
- **WHEN** developer mode is active and the user selects "Fiscalizador MF"
- **THEN** a dialog opens with actions: Connect, Status (ENQ), Data (S1), Payment Methods (S4), IGTF info (S3+S25), Report X, Report Z, and raw command input

### Requirement: Systray Connection Status
The system SHALL display a printer icon in the backend systray indicating Web Serial connection status with manual connect/disconnect capability.

#### Scenario: Auto-reconnect on page load
- **WHEN** the page loads and a previously authorized port exists
- **THEN** the system silently auto-connects; on success the icon turns green

#### Scenario: Manual connect can authorize a new port
- **WHEN** the user clicks the systray icon while disconnected
- **THEN** a silent reconnect is attempted first, and if it fails the Web Serial permission prompt (`requestPermission: true`) is triggered so the backend can authorize a port for the first time (fix of the v17 behavior where the prompt was never reachable)

#### Scenario: Status polling
- **WHEN** the systray is mounted
- **THEN** the badge re-syncs with the shared driver every 5 seconds (covers connections made by other components)

### Requirement: Company Settings
The system SHALL add fiscal printer configuration fields to company settings.

#### Scenario: Configure print type
- **WHEN** `invoice_print_type` is "fiscal" on the company
- **THEN** the MF buttons are visible on invoices and the free-form print button is hidden; when "free", normal free-form printing applies

#### Scenario: Configure Flag 21
- **WHEN** `mf_flag_21` is set on the company (00, 01, 02, or 30)
- **THEN** the numeric format for amounts, quantities and payments sent to the printer is adjusted accordingly

### Requirement: Chatter Failure Logging
The system SHALL log fiscal printer failures to the invoice chatter for audit trail.

#### Scenario: Log print failure
- **WHEN** any fiscal printing operation fails (no Web Serial support, no connection, driver error, reprint error)
- **THEN** a `message_post` is added to the invoice chatter with the action name and failure reason

### Requirement: Coexistence with the POS module
The system SHALL define the shared fields with the same names as `l10n_ve_pos_mf` so both modules can be installed together.

#### Scenario: Shared account.move fields
- **WHEN** both modules are installed
- **THEN** `mf_invoice_number`, `mf_serial`, `mf_reportz` on `account.move` and `fiscal_code` on `account.tax` are single fields (merged definitions), and `account.move.report_z` also updates pending `pos.order` records (POS override chains via super)
