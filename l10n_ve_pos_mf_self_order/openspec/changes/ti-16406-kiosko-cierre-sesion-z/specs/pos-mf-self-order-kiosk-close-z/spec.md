# Spec delta: pos-mf-self-order-kiosk-close-z

## ADDED Requirements

### Requirement: El panel de Debug del Kiosko fiscal cierra la sesión con Reporte Z

Con `l10n_ve_pos_mf_self_order` instalado, el panel de Debug del Kiosko
(`?debug=1`) SHALL ofrecer **Cerrar sesión e imprimir Z**, con el mismo orden
que el botón de la caja (`ClosePosPopup.closeSessionAndPrintZ` de
`l10n_ve_pos_mf`): órdenes pendientes, confirmación, Reporte Z, lectura de S1,
sincronización con Odoo y cierre nativo de la sesión. Un fallo en cualquier
paso SHALL detener los siguientes y avisar al operador.

#### Scenario: Cierre completo

- **GIVEN** un Kiosko con sesión abierta y todas sus órdenes pagadas con
  número fiscal
- **WHEN** el operador pulsa "Cerrar sesión e imprimir Z" y confirma
- **THEN** la máquina imprime la Z, el puerto se libera, la sesión guarda el
  número de Z, las órdenes de esa máquina sin Z quedan marcadas, la sesión
  queda cerrada y el Kiosko deja de recibir pedidos

#### Scenario: El operador no confirma

- **GIVEN** el diálogo "El Reporte Z cerrará el día fiscal actual"
- **WHEN** el operador cancela
- **THEN** no se imprime la Z ni se cierra la sesión

#### Scenario: La Z no se imprime

- **GIVEN** la máquina no conectada o un error del comando de la Z
- **WHEN** el operador confirma
- **THEN** se avisa del error y no se sincroniza ni se cierra la sesión

#### Scenario: La Z sale pero Odoo no se actualiza

- **GIVEN** la Z impresa sin S1 legible, o un error al sincronizarla
- **WHEN** termina la impresión
- **THEN** se avisa que la Z ya salió y que hay que revisar el libro de ventas
  y cerrar desde el backend; la sesión no se cierra

### Requirement: Sin Z ni cierre con órdenes sin número fiscal

El cierre con Z SHALL bloquearse si la sesión abierta tiene órdenes sin
`mf_invoice_number` que no estén canceladas ni en borrador (los borradores
son carritos sin pagar que el cierre nativo del Kiosko borra). El aviso SHALL
listar hasta 10 órdenes y remitir al panel de órdenes para facturarlas o
imprimirlas. La ruta de cierre SHALL repetir la revisión en el servidor.

#### Scenario: Orden pagada sin factura fiscal

- **GIVEN** una orden pagada de la sesión sin número fiscal (con o sin factura
  contable)
- **WHEN** el operador pulsa "Cerrar sesión e imprimir Z"
- **THEN** ve la lista de órdenes pendientes y no se imprime la Z ni se cierra
  la sesión

#### Scenario: Llamada directa a la ruta de cierre

- **GIVEN** una orden pendiente en la sesión
- **WHEN** alguien llama `/l10n_ve_pos_mf_self_order/kiosk/close_session` con
  el token de la caja
- **THEN** la ruta responde `success: false` con las órdenes pendientes y la
  sesión sigue abierta

#### Scenario: Carritos sin pagar

- **GIVEN** solo órdenes en borrador y órdenes con número fiscal
- **WHEN** el operador cierra con Z
- **THEN** no hay bloqueo y el cierre borra los borradores

### Requirement: La sincronización de la Z solo toca las máquinas de su caja

La ruta `report_z` SHALL validar el `access_token` con `_verify_pos_config`,
rechazar datos sin `valid`, sin el serial de la máquina o sin un contador de Z
entero, y guardar la Z en la sesión abierta de esa caja. Las facturas y
órdenes sin Z SHALL marcarse solo si la caja ya imprimió con esa máquina
(alguna de sus órdenes tiene ese `fiscal_machine`).

#### Scenario: Serial de otra máquina

- **GIVEN** facturas sin Z de una máquina con la que la caja nunca imprimió
- **WHEN** el Kiosko sincroniza una Z con ese serial
- **THEN** esas facturas no cambian y la sesión de la caja guarda su Z

#### Scenario: Datos de la Z inválidos

- **GIVEN** un `value` sin `valid`, sin serial o con un contador que no es
  entero
- **WHEN** llega a `report_z`
- **THEN** la ruta responde `success: false` y la sesión no guarda Z

### Requirement: El cierre desde el Kiosko no deja cambios a medias

La ruta `close_session` SHALL cerrar la sesión abierta de la caja del
`access_token` con `pos.config.action_close_kiosk_session`. Si el cierre
nativo falla o no deja la sesión cerrada, la ruta SHALL responder con error y
la petición SHALL revertirse completa: la sesión sigue abierta.

#### Scenario: El cierre nativo no termina

- **GIVEN** un asiento de cierre que no cuadra (el cierre nativo revierte y
  devuelve el asistente de diferencias) o un error del cierre
- **WHEN** el Kiosko llama la ruta de cierre
- **THEN** la ruta responde con el error, la sesión sigue abierta y el panel
  indica cerrarla desde el backend
