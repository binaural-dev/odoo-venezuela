## MODIFIED Requirements

### Requirement: El panel de Debug del Kiosko fiscal cierra la sesión con Reporte Z

Con `l10n_ve_pos_mf_self_order` instalado y la máquina fiscal activa en la
caja (`access_button_mf`), el panel de Debug del Kiosko (`?debug=1`) SHALL
ofrecer **Cerrar sesión e imprimir Z**, con el mismo orden
que el botón de la caja (`ClosePosPopup.closeSessionAndPrintZ` de
`l10n_ve_pos_mf`): órdenes pendientes, confirmación, lectura de S1, Reporte Z,
sincronización con Odoo, cierre nativo de la sesión y vuelta al menú de
selección de cajas del PdV. S1 SHALL leerse antes de la Z, como el flujo IoT:
su contador es el de la última Z y el servidor le suma 1. Un fallo en
cualquier paso SHALL detener los siguientes y avisar al operador.

#### Scenario: Cierre completo

- **GIVEN** un Kiosko con sesión abierta y todas sus órdenes pagadas con
  número fiscal
- **WHEN** el operador pulsa "Cerrar sesión e imprimir Z" y confirma
- **THEN** la máquina imprime la Z, el puerto se libera, la sesión guarda el
  número de esa Z (si la última era la 0146, guarda 147), las órdenes de esa
  máquina sin Z quedan marcadas, la sesión queda cerrada y el Kiosko pasa al
  menú de selección de cajas del PdV
  (`/odoo/action-point_of_sale.action_client_pos_menu`)

#### Scenario: Caja sin máquina fiscal

- **GIVEN** un Kiosko cuya caja no tiene `access_button_mf`
- **WHEN** el operador abre el panel de Debug
- **THEN** no ve el botón "Cerrar sesión e imprimir Z"

#### Scenario: El operador no confirma

- **GIVEN** el diálogo "El Reporte Z cerrará el día fiscal actual"
- **WHEN** el operador cancela
- **THEN** no se imprime la Z ni se cierra la sesión

#### Scenario: La Z no se imprime

- **GIVEN** la máquina no conectada, un S1 sin serial o sin contador de Z, o
  un error del comando de la Z
- **WHEN** el operador confirma
- **THEN** se avisa del error, la Z no sale, no se sincroniza ni se cierra la
  sesión y el Kiosko sigue en pantalla

#### Scenario: La Z sale pero Odoo no se actualiza

- **GIVEN** un error al sincronizar con Odoo la Z ya impresa
- **WHEN** termina la impresión
- **THEN** se avisa que la Z ya salió y que hay que revisar el libro de ventas
  y cerrar desde el backend; la sesión no se cierra y el Kiosko sigue en
  pantalla
