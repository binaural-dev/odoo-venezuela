## 1. Shared pairing helper

- [x] 1.1 Replace `ensureConnected()` with `ensurePaired()` in `mf_webserial_service.js`: verify/request device authorization without leaving the port open (pairing probe: connect+disconnect if not yet authorized).

## 2. One-shot print/report buttons

- [x] 2.1 `mf_webserial_button.js`: `printDocument()` pairs via `ensurePaired()`, then prints inside `driver.withConnection()`.
- [x] 2.2 `mf_webserial_button.js`: `reprintDocument()` follows the same pair-then-`withConnection()` pattern.
- [x] 2.3 `mf_reports_webserial_button.js`: `_connectDriver()` uses `ensurePaired()` instead of holding a connection open.
- [x] 2.4 `mf_reports_webserial_button.js`: `executeAction()` validates date ranges before touching the hardware, then runs Report X / Report Z (+ S1 sync) / print-by-date / reprint-by-date inside a single `driver.withConnection()` cycle.

## 3. Fiscalizador interactive dialog

- [x] 3.1 `mf_fiscalizador_dialog.js`: "Conectar" pairs via `ensurePaired()` and opens the session with `driver.acquireConnection()`, tracked by `this._connectionAcquired`.
- [x] 3.2 `mf_fiscalizador_dialog.js`: all other actions (Status, S1, S4, IGTF info, Report X, Report Z, raw command) guard on `this._connectionAcquired` instead of reconnecting.
- [x] 3.3 `mf_fiscalizador_dialog.js`: `onWillUnmount` releases the connection via `driver.releaseConnection()` if one was acquired.

## 4. Systray

- [x] 4.1 `mf_systray.js`: remove `onMounted` auto-connect-and-hold-open; replace with a paired/not-paired check via `navigator.serial.getPorts()`.
- [x] 4.2 `mf_systray.js`: click handler pairs via connect+disconnect probe when not paired, or runs a one-shot `driver.withConnection(() => driver.getStatus())` communication test when already paired.
- [x] 4.3 `mf_systray.js`: replace the 5s `driver.isConnected` poll with a 10s `getPorts()`-based pairing poll (no port access).

## 5. Verification

- [x] 5.1 Syntax-check all five modified files (`node --check`).
- [ ] 5.2 Manual browser test: open backend (Facturación) in one tab and POS in another, confirm an idle backend tab no longer blocks the POS from using the fiscal printer, and that print/report/Fiscalizador flows still work end to end.
- [ ] 5.3 Commit and push once 5.2 is confirmed.
