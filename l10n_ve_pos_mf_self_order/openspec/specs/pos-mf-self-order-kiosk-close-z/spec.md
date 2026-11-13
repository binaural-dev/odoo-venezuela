# pos-mf-self-order-kiosk-close-z Specification

## Purpose
Cerrar la sesión del Kiosko (`pos_self_order` en modo `kiosk`) con su
Reporte Z desde el panel de Debug, cuando la máquina fiscal TFHKA está
conectada al equipo del Kiosko por Web Serial: mismo flujo que el botón
"Cerrar sesión e imprimir Z" de la caja (`l10n_ve_pos_mf`), con rutas
públicas limitadas a la caja del Kiosko (ticket 16406).

## Requirements

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

#### Scenario: La máquina no confirma la Z

- **GIVEN** la máquina sin papel, que no responde al `I0Z`
- **WHEN** el S1 leído después no muestra el contador de Z avanzado
- **THEN** se avisa "Reporte Z sin confirmar" (revisar la máquina y no repetir
  la Z si salió), no se sincroniza ni se cierra la sesión; si el contador sí
  avanzó, se sincroniza con la Z que salió y se cierra

### Requirement: Una sola Z por sesión y nunca en medio de una factura

El cierre con Z SHALL NOT empezar si hay una factura fiscal imprimiéndose en
el Kiosko, ni si la sesión ya registró su Z: en ese caso SHALL avisar que se
cierre desde el backend.

#### Scenario: La sesión ya tiene su Z

- **GIVEN** una sesión con Reporte Z registrado cuyo cierre falló
- **WHEN** el operador vuelve a pulsar "Cerrar sesión e imprimir Z"
- **THEN** ve el número de esa Z y la indicación de cerrar desde el backend, y
  la máquina no imprime otra Z

#### Scenario: Factura fiscal en curso

- **GIVEN** el Kiosko imprimiendo una factura fiscal
- **WHEN** el operador pulsa "Cerrar sesión e imprimir Z"
- **THEN** no se consulta la sesión ni se toca la máquina

### Requirement: Sin Z ni cierre con órdenes sin número fiscal

El cierre con Z SHALL bloquearse si la sesión abierta tiene órdenes sin
`mf_invoice_number` que no estén canceladas, salvo los borradores sin pago
(carritos que el cierre nativo del Kiosko borra). Un borrador con pago SHALL
bloquear. El aviso SHALL listar hasta 10 órdenes y abrir el panel de Órdenes
con las pendientes cargadas; los borradores con pago SHALL indicarse para
resolver desde el backend. La ruta de cierre SHALL repetir la revisión.

#### Scenario: Orden pagada sin factura fiscal

- **GIVEN** una orden pagada de la sesión sin número fiscal (con o sin factura
  contable)
- **WHEN** el operador pulsa "Cerrar sesión e imprimir Z"
- **THEN** ve la lista de órdenes pendientes, puede abrir el panel de Órdenes
  donde aparecen aunque no estén entre las últimas, y no se imprime la Z ni se
  cierra la sesión

#### Scenario: Borrador con pago

- **GIVEN** una orden de la sesión en borrador con un pago (cobro cuya
  finalización quedó a medias)
- **WHEN** el operador pulsa "Cerrar sesión e imprimir Z"
- **THEN** el aviso la lista para resolverla desde el backend y la sesión no
  se cierra (el cierre nativo la borraría)

#### Scenario: Llamada directa a la ruta de cierre

- **GIVEN** una orden pendiente en la sesión
- **WHEN** alguien llama `/l10n_ve_pos_mf_self_order/kiosk/close_session` con
  el token de la caja
- **THEN** la ruta responde `success: false` con las órdenes pendientes y la
  sesión sigue abierta

#### Scenario: Carritos sin pagar

- **GIVEN** solo borradores sin pago y órdenes con número fiscal
- **WHEN** el operador cierra con Z
- **THEN** no hay bloqueo y el cierre borra los borradores

### Requirement: Las rutas del cierre con Z son solo para el Kiosko

Las rutas `close_session/check`, `report_z` y `close_session` SHALL validar el
`access_token` con `_verify_pos_config` y SHALL rechazar las cajas que no estén
en modo kiosko: el token del autopedido por QR va impreso en las mesas.

#### Scenario: Token del QR de una mesa

- **GIVEN** una caja de autopedido por QR (`self_ordering_mode = mobile`) con
  sesión abierta
- **WHEN** alguien llama cualquiera de las tres rutas con su token
- **THEN** la ruta responde con error, la sesión sigue abierta y sin Z

#### Scenario: Token inválido

- **WHEN** alguien llama las rutas con un token que no es de ninguna caja
- **THEN** responden con error

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
