## ADDED Requirements

### Requirement: Native close session button for authorized users
The system SHALL show an additional "Cerrar sesión" button in the POS
closing popup, alongside the existing dual fiscal flow (Reporte X / Cerrar
sesion e imprimir Z), for users in the `l10n_ve_pos_mf.group_pos_close_native`
group.

#### Scenario: User with the group sees three buttons
- **WHEN** a cashier with `group_pos_close_native` opens the closing popup
- **THEN** the popup shows "Reporte X", "Cerrar sesion e imprimir Z", and
  "Cerrar sesión"

#### Scenario: User without the group sees only the dual flow
- **WHEN** a cashier without `group_pos_close_native` opens the closing
  popup
- **THEN** the popup shows only "Reporte X" and "Cerrar sesion e imprimir Z",
  unchanged from current behavior

### Requirement: Native close bypasses fiscal validations
The native "Cerrar sesión" button MUST close the POS session using Odoo's
native `confirm()` flow, without printing the Z report and without
validating that all session orders are invoiced in the fiscal machine.

#### Scenario: Close with unfiscalized orders
- **WHEN** a user with `group_pos_close_native` clicks "Cerrar sesión" while
  the session has orders with an empty `mf_invoice_number`
- **THEN** the session closes normally, without blocking on unfiscalized
  orders and without printing a Z report

### Requirement: Permission exposed to the POS frontend
The system SHALL expose whether the current user belongs to
`l10n_ve_pos_mf.group_pos_close_native` to the POS frontend as
`_can_close_session_native`, computed server-side via `_load_pos_data_read`.

#### Scenario: Frontend reads the permission
- **WHEN** the POS session loads data for the current user
- **THEN** `pos.user._can_close_session_native` reflects the user's
  membership in `group_pos_close_native`
