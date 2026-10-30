## Why

The Accounting/Facturación backend (`l10n_ve_iot_mf`) held the Web Serial port open indefinitely: the systray auto-connected on every backend page load and never released it, and the print/report/fiscalizador flows connected on demand but never disconnected afterward. A single idle backoffice tab therefore monopolized the fiscal printer's COM port, blocking the POS (`l10n_ve_pos_mf`, which already uses a correct on-demand connection model) or any other tab from talking to the same device.

## What Changes

- `mf_webserial_service.js`: replace `ensureConnected()` (connects and leaves the port open) with `ensurePaired()` (verifies/requests device authorization via a brief connect+disconnect probe, never holds the port open).
- `mf_webserial_button.js` (invoice/credit-note/debit-note print, reprint): pair via `ensurePaired()`, then perform the actual print inside `driver.withConnection()` so the port opens only for the duration of that one operation.
- `mf_reports_webserial_button.js` (Report X/Z, date-range print/reprint): same on-demand pattern; Report Z's S1 sync now runs inside the same `withConnection()` cycle as the Z print itself.
- `mf_fiscalizador_dialog.js`: since it's an interactive multi-command console, keep the port open for the dialog's lifetime via `driver.acquireConnection()`/`releaseConnection()` (ref-counted, shared with `withConnection()`), always releasing on `onWillUnmount`.
- `mf_systray.js` (**BREAKING** behavior change): no longer auto-connects and holds the port open on page load. It now shows "paired" vs "not paired" using `navigator.serial.getPorts()` (never opens the port), pairs via a connect+disconnect probe on click, and tests communication via `withConnection()` when already paired.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `l10n_ve_iot_mf`: the "Systray Connection Status" requirement changes from "auto-reconnect and stay connected, poll every 5s" to "show pairing status without holding the port open, connect on demand per operation". The "Invoice Fiscal Printing", "MF Reports Wizard", and "Fiscalizador" requirements gain an on-demand-connection scenario (port opens only for the duration of each operation, or for the Fiscalizador dialog's lifetime).

## Impact

- Affected files: `l10n_ve_iot_mf/static/src/backend/{mf_webserial_service,mf_webserial_button,mf_reports_webserial_button,mf_fiscalizador_dialog,mf_systray}.js`.
- No Python/model changes, no migrations needed — purely a JS connection-lifecycle fix.
- Depends on `TfhkaDriver.withConnection`/`acquireConnection`/`releaseConnection` from `l10n_ve_mf_base`, already used successfully by `l10n_ve_pos_mf`.
- Not addressed here (verified already correct, no change needed): module dependency graph — `l10n_ve_pos_mf` and `l10n_ve_iot_mf` already depend only on `l10n_ve_mf_base`, not on each other.
