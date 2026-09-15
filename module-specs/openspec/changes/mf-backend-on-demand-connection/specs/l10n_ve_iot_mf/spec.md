## MODIFIED Requirements

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

#### Scenario: Port opens on demand for the print operation only
- **WHEN** the user clicks a fiscal print/reprint action
- **THEN** the system first ensures the device is paired (`ensurePaired()`, a brief connect+disconnect probe if not yet authorized in this browser — never left open)
- **AND** the actual print/reprint runs inside `driver.withConnection()`, which opens the serial port only for that operation's duration and releases it in a `finally` regardless of success or failure
- **AND** an idle backend tab that isn't actively printing never holds the port, so it does not block the POS or another tab from using the same fiscal printer

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

#### Scenario: Date validation runs before opening the port
- **WHEN** the action is "print_resume_date" or "reprint_invoices_date"
- **THEN** the date range is parsed and validated before pairing/connecting, so an invalid date range never triggers a serial port open

#### Scenario: Each report action opens and releases the port on demand
- **WHEN** any wizard action (Report X, Report Z, print-by-date, reprint-by-date) runs
- **THEN** the device is paired via `ensurePaired()` (no port left open), and the entire action — including the S1 sync that follows a successful Report Z — executes inside one `driver.withConnection()` cycle
- **AND** the port is released as soon as the action (and, for Report Z, its Odoo sync) completes

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

#### Scenario: Port stays open for the dialog's session, released on close
- **WHEN** the user clicks "Conectar"
- **THEN** the system pairs if needed (`ensurePaired()`) and opens the port for the session via `driver.acquireConnection()`, so subsequent clicks (Status, S1, S4, raw commands, reports) reuse the same open port without reconnecting each time
- **AND** every other action in the dialog requires that an active session was acquired first, showing an error log entry ("Presiona Conectar primero") otherwise
- **AND** closing the dialog (including via `onWillUnmount`) always calls `driver.releaseConnection()` if a session was acquired, so the port is never left open after the dialog is gone

### Requirement: Systray Connection Status
The system SHALL display a printer icon in the backend systray indicating whether the fiscal machine device is paired (authorized) in this browser, with the ability to pair a new device or test communication on click — without holding the serial port open outside of an active operation.

#### Scenario: Show not-paired state
- **WHEN** no fiscal printer device is authorized in this browser (`navigator.serial.getPorts()` is empty)
- **THEN** the systray icon is grey with tooltip "Máquina Fiscal: No pareada (click para parear)"

#### Scenario: Detect paired state without opening the port
- **WHEN** the systray mounts, and every 10 seconds afterward
- **THEN** the system checks `navigator.serial.getPorts()` (never opens the port) to determine whether the device is paired
- **AND** the icon turns green ("Pareada") if a paired device is found, grey otherwise

#### Scenario: Pair a new device
- **WHEN** the user clicks the systray icon while not paired
- **THEN** the system calls `driver.connect({ requestPermission: true })` to trigger the Web Serial device chooser
- **AND** immediately calls `driver.disconnect()` after a successful pairing, so the port is not left open
- **AND** the icon turns green and a success notification is shown

#### Scenario: Test communication when already paired
- **WHEN** the user clicks the systray icon while already paired
- **THEN** the system runs `driver.withConnection(() => driver.getStatus())`, opening the port only for that ENQ round-trip and releasing it immediately after
- **AND** a notification reports whether the printer responded

#### Scenario: No periodic port polling
- **WHEN** the systray is mounted and idle (not mid-click)
- **THEN** it never opens the serial port on its own — only `getPorts()` (pairing-only, no hardware access) runs on the 10-second interval
