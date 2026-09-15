# l10n_ve_iot_mf — Accounting / Invoicing Fiscal Machine Integration

## Purpose

Integrates TFHKA fiscal printers with Odoo Accounting (Facturación/Contabilidad) via Web Serial API. Handles invoice/refund/debit-note printing from `account.move` form view, fiscalizador (debug) tool, systray connection status, MF reports wizard (X, Z, date-range print, date-range reprint), company-level configuration (`mf_flag_21`, `invoice_print_type`), and persistence of fiscal metadata on invoices.

## Requirements

### Requirement: Invoice Fiscal Printing from Form View
The system SHALL allow printing fiscal documents (invoice, credit note, debit note) directly from the `account.move` form view via Web Serial API.

#### Scenario: Print customer invoice
- **WHEN** the user clicks "Print MF Invoice" on a validated `out_invoice`
- **THEN** the system checks `check_print_out_invoice()` (date validation, partner VAT, invoice lines)
- **AND** sends the complete command sequence to the fiscal printer via `TfhkaDriver.printInvoice`
- **AND** persists `mf_invoice_number`, `mf_serial`, `mf_reportz`, and optionally `iot_mf` on the invoice
- **AND** logs failures to the chatter via `log_mf_print_failure`

#### Scenario: Date validation uses user timezone
- **WHEN** checking that the invoice date is not in the future
- **THEN** `fields.Date.context_today(self)` is used (respects user timezone) instead of `fields.Date.today()` (UTC)

#### Scenario: Line discount applied before sending to printer
- **WHEN** invoice lines have a discount percentage
- **THEN** `price_vef = price_vef * (1 - line.discount / 100.0)` is applied in `check_print_*` methods
- **AND** no `q-` discount commands are sent (the driver receives pre-discounted prices)

#### Scenario: iot_mf resolved by serial after printing
- **WHEN** printing succeeds and a serial is returned from S1
- **THEN** the system searches for an `iot.device` with matching `serial_machine`
- **AND** if found, sets `iot_mf` on the invoice; if not found, logs a warning to chatter

### Requirement: MF Reports Wizard
The system SHALL provide a wizard accessible from the "Detalle de Ventas" menu for fiscal report operations.

#### Scenario: Print Report X
- **WHEN** the user clicks "Imprimir Reporte X" with the fiscal printer connected
- **THEN** the driver sends the I0X command and the printer prints the X summary

#### Scenario: Print Report Z with backend sync
- **WHEN** the user confirms "Imprimir Reporte Z" (after explicit confirmation dialog)
- **THEN** the driver sends I0Z, reads S1 to get the new counter, and calls `account.move.report_z()` to sync all pending invoices in Odoo

#### Scenario: Print resume by date range (I2S)
- **WHEN** the user selects date_from and date_to and clicks "Impresion por rango de fecha"
- **THEN** the system reads dates from the form record (no RPC to wizard model)
- **AND** formats dates to DDMMYY and sends the I2S command with 30s timeout
- **AND** validates that date_to >= date_from

#### Scenario: Reprint invoices by date range (Rf)
- **WHEN** the user selects date_from and date_to and clicks "Reimpresion facturas por fecha"
- **THEN** the system reads dates from the form record, pads to 7 digits, and sends the Rf command with 60s timeout
- **AND** date parsing handles multiple formats: YYYY-MM-DD, DD/MM/YYYY, Date objects, and Luxon DateTime objects

### Requirement: Fiscalizador (Debug Tool)
The system SHALL provide a debug dialog accessible from the Developer Tools menu (bug icon) for technical diagnostics.

#### Scenario: Open fiscalizador
- **WHEN** developer mode is active and the user selects "Fiscalizador MF" from the debug menu
- **THEN** a dialog opens with actions: Connect, Status (ENQ), Data (S1), Payment Methods (S4), Report X, Report Z, and raw command input

#### Scenario: Query payment methods (S4)
- **WHEN** the user clicks "Medios de Pago (S4)"
- **THEN** the driver sends the S4 command, parses the response into method code/name pairs, and displays them in the log

#### Scenario: Send raw command
- **WHEN** the user types a TFHKA command (e.g., "S3", "D") in the raw input
- **THEN** the command is sent directly and the response is displayed

### Requirement: Systray Connection Status
The system SHALL display a printer icon in the backend systray indicating Web Serial connection status with manual connect/disconnect capability.

#### Scenario: Show disconnected state
- **WHEN** no fiscal printer is connected
- **THEN** the systray icon is grey with tooltip "Impresora Fiscal Desconectada"

#### Scenario: Auto-reconnect on page load
- **WHEN** the page loads and a previously authorized port exists
- **THEN** the system silently attempts auto-connection via `autoConnect()`
- **AND** on success the icon turns green; on failure it remains grey

#### Scenario: Manual connect/disconnect
- **WHEN** the user clicks the systray icon
- **THEN** if disconnected, it triggers `requestPort()` for new connection
- **AND** if connected, it disconnects

#### Scenario: Status polling
- **WHEN** connected
- **THEN** the system polls the printer every 5 seconds via ENQ
- **AND** on detection of disconnection, reveals the icon as red with an error state

### Requirement: Company Settings
The system SHALL add fiscal printer configuration fields to company settings.

#### Scenario: Configure print type
- **WHEN** `invoice_print_type` is set to "fiscal" on the company
- **THEN** invoices use fiscal printing via Web Serial; when set to "free", normal PDF printing is used

#### Scenario: Configure Flag 21
- **WHEN** `mf_flag_21` is set on the company (00, 01, 02, or 30)
- **THEN** the numeric format (integer/decimal digits) for amounts, quantities, and payments is adjusted accordingly

### Requirement: Migration from Legacy IoT
The system SHALL migrate existing IoT Box fiscal printer configuration to the Web Serial API model via post-migration scripts.

#### Scenario: Inherit flag_21 from IoT device
- **WHEN** the module is upgraded from 17.0.0.2.0
- **THEN** the `mf_flag_21` on `res.company` is set from the associated `iot.device` with `serial_machine` configured
- **AND** legacy `flag_21` and `phone_line` values are preserved but deprecated

### Requirement: Chatter Failure Logging
The system SHALL log fiscal printer failures to the invoice chatter for audit trail.

#### Scenario: Log print failure
- **WHEN** any fiscal printing operation fails (no Web Serial, no connection, driver error, reprint error)
- **THEN** a `message_post` is added to the invoice chatter with the action name and failure reason

### Requirement: Fiscal Machine Group in Form View
The system SHALL display a single "Fiscal Machine" group in the "Otra información" tab of `account.move` form view showing fiscal metadata.

#### Scenario: No duplicate sections
- **WHEN** both `l10n_ve_iot_mf` and `l10n_ve_pos_mf` are installed
- **THEN** only one "Fiscal Machine" group appears (the `l10n_ve_iot_mf` one)
- **AND** the POS-specific `cashbox_id` field is still present

#### Scenario: No duplicate fiscal_code field on account.tax form
- **WHEN** both `l10n_ve_iot_mf` and `l10n_ve_pos_mf` are installed
- **THEN** the `fiscal_code` field appears only once in the tax form (provided by `l10n_ve_pos_mf`, which has the more descriptive label "Código Fiscal (Máquina Fiscal)")
- **AND** the `17.0.0.3.0` post-migration (the same one that inherits `mf_flag_21` from the legacy `iot.device`) also removes the orphaned duplicate view (`l10n_ve_iot_mf.view_account_tax_form`) from any database upgrading from an older version, in a single migration step (no separate version bump needed for this cosmetic fix)

### Requirement: Spanish Translation
The system SHALL provide Spanish (es_VE) translations for all user-facing terms.

#### Scenario: Translated wizard fields
- **WHEN** the user language is Spanish (VE)
- **THEN** "Date From" displays as "Fecha desde" and "Date To" as "Fecha hasta"
- **AND** "Fiscal Machine" displays as "Maquina fiscal"
