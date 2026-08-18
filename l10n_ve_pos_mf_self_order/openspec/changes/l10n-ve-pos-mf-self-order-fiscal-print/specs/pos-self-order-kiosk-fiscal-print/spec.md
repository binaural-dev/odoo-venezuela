# Spec delta: pos-self-order-kiosk-fiscal-print

## ADDED Requirements

### Requirement: Registrar-primero — nunca imprimir sin orden en Odoo

El sistema SHALL registrar la orden del Kiosko en Odoo (crear `pos.order` +
`account.move`) ANTES de imprimir la factura fiscal, e imprimir SOLO cuando la
orden ya existe en Odoo. Nunca debe emitirse una factura fiscal (número SENIAT)
sin su orden/factura en Odoo.

#### Scenario: Orden registrada y confirmada en el Kiosko

- **GIVEN** una caja en modo Kiosko con `l10n_ve_pos_mf_self_order` instalado, la
  máquina fiscal conectada, y el pago aprobado
- **WHEN** la orden se registra en el servidor y el cliente llega a la pantalla de
  confirmación (`confirmationPage`)
- **THEN** recién ahí se imprime la factura fiscal en la máquina, tomando el pago
  de `order.payment_ids`, y el número resultante se persiste en la orden y en el
  `account.move` vía `write_mf_invoice_data`

#### Scenario: Servidor Odoo no accesible al momento del pago

- **GIVEN** una orden del Kiosko cuyo pago fue aprobado, con el servidor Odoo
  temporalmente no accesible
- **WHEN** el cliente finaliza la orden
- **THEN** la orden se encola localmente Y se imprime igual (la orden existe en la
  cola local, el papel fiscal no es huérfano); el `mf_invoice_number` impreso se
  mete en el payload encolado y, al volver la conexión, la orden se registra en
  Odoo con su número fiscal — igual que el PoS normal offline

#### Scenario: La impresión falla con la orden ya registrada

- **GIVEN** una orden del Kiosko ya registrada y facturada en Odoo, sin
  `mf_invoice_number`, y la máquina fiscal no disponible
- **WHEN** se intenta imprimir en la confirmación y falla
- **THEN** la orden queda "pendiente de imprimir" (registrada, sin número fiscal),
  se avisa el motivo, y puede reimprimirse luego (menú Debug MF), que persiste el
  número con `write_mf_invoice_data`

### Requirement: El número fiscal se persiste en Odoo (orden + account.move)

El sistema SHALL persistir `mf_invoice_number`/`fiscal_machine`/`mf_reportz` en la
`pos.order` y propagarlos al `account.move` tras imprimir, reutilizando
`pos.order.write_mf_invoice_data`, expuesto al Kiosko público mediante un endpoint
dedicado que valida el `access_token` y que la orden pertenezca a la caja.

#### Scenario: Tras imprimir se persiste el número en orden y factura

- **GIVEN** una orden del Kiosko registrada en Odoo que acaba de imprimirse en la
  máquina fiscal, obteniendo un `mf_invoice_number`
- **WHEN** el cliente invoca el endpoint público de persistencia con el número, el
  serial y el `access_token` de la caja
- **THEN** el servidor escribe `mf_invoice_number`/`fiscal_machine`/`mf_reportz` en
  la `pos.order` y los propaga al `account.move` asociado

#### Scenario: El endpoint rechaza una orden ajena a la caja

- **GIVEN** un `access_token` de una caja y un `order_id` que no pertenece a esa
  caja
- **WHEN** se invoca el endpoint de persistencia
- **THEN** no se escribe nada y se devuelve un error ("Orden no encontrada para
  esta caja")

### Requirement: El bus de pago del Kiosko incluye los pagos

El sistema SHALL incluir los registros `pos.payment` en el evento `PAYMENT_STATUS`
que el Kiosko emite al cliente, de modo que la orden confirmada tenga sus pagos en
el cliente y la impresión fiscal pueda derivar el método (`code_fiscal_printer`) y
el monto.

#### Scenario: La confirmación recibe los pagos

- **GIVEN** una orden del Kiosko registrada y pagada
- **WHEN** el servidor emite `PAYMENT_STATUS` al confirmar
- **THEN** el `data` del evento incluye `pos.payment` (además de `pos.order` y
  `pos.order.line`), y en el cliente `order.payment_ids` queda poblado tras
  `connectNewData`

### Requirement: El panel de órdenes fiscales persiste entre sesiones

El sistema SHALL poblar el panel de órdenes fiscales del Kiosko con las órdenes
recientes de la caja traídas del servidor (no solo las que queden en memoria del
cliente), para que no se pierdan al iniciar una orden nueva o recargar.

#### Scenario: El panel muestra órdenes de turnos anteriores

- **GIVEN** una caja con órdenes registradas en sesiones ya cerradas
- **WHEN** el operador abre el panel de órdenes fiscales (o pulsa "Actualizar")
- **THEN** el panel las lista (últimas N de la caja) con su estado fiscal, y
  permite imprimir las pendientes o reimprimir la copia de las ya emitidas

### Requirement: La impresión fiscal del Kiosko es idempotente

El sistema SHALL evitar reimprimir o volver a cobrar una orden del Kiosko cuando
la finalización se reintenta.

#### Scenario: Reintento de una orden ya impresa

- **GIVEN** una orden del Kiosko que ya tiene `mf_invoice_number`
- **WHEN** el flujo de finalización se reintenta (p. ej. tras un fallo de red del
  RPC de registro)
- **THEN** no se emite un segundo comprobante fiscal ni se recobra la tarjeta; se
  reintenta solo el registro de la orden

### Requirement: Panel de órdenes fiscales del Kiosko (imprimir / reimprimir copia)

El sistema SHALL ofrecer, desde el modo debug, un panel estilo TicketScreen que
liste las órdenes de la sesión y, al seleccionar una, muestre su resumen (cliente,
líneas, total, estado fiscal) con una acción que IMPRIME la factura fiscal si la
orden aún no tiene número, o REIMPRIME una COPIA si ya lo tiene.

#### Scenario: Imprimir una orden pendiente

- **GIVEN** una orden del Kiosko registrada y pagada, sin `mf_invoice_number`, y
  la máquina fiscal conectada
- **WHEN** el operador la selecciona en el panel y pulsa "Imprimir factura fiscal"
- **THEN** se imprime en la máquina, el número resultante se guarda en la orden y
  se propaga al `account.move` (`write_mf_invoice_data`)

#### Scenario: Reimprimir la copia de una factura ya emitida

- **GIVEN** una orden del Kiosko con `mf_invoice_number` (ya impresa) y la máquina
  conectada
- **WHEN** el operador la selecciona y pulsa "Reimprimir copia"
- **THEN** la máquina reimprime una COPIA del documento por su número
  (`TfhkaDriver.reprintDocument`), sin emitir un documento nuevo ni cambiar la
  numeración

### Requirement: Exposición de datos fiscales al cliente del Kiosko

El sistema SHALL exponer al cliente del Kiosko (vía `_load_pos_self_data_fields`)
los campos fiscales que el armado del payload y la sincronización requieren, ya
que el Kiosko usa loaders con lista explícita distintos del loader de caja.

#### Scenario: El cliente del Kiosko recibe los campos fiscales

- **GIVEN** una caja en modo Kiosko con `l10n_ve_pos_mf_self_order` instalado
- **WHEN** el Kiosko carga su dataset
- **THEN** `pos.config` trae los campos de la máquina fiscal (`flag_21`,
  `serial_machine`, `has_cashbox`, etc.), `pos.payment.method` trae
  `code_fiscal_printer`, `account.tax` trae `fiscal_code`, y `pos.order` trae
  `mf_invoice_number`/`fiscal_machine`/`mf_reportz`

### Requirement: El cliente ve feedback mientras se imprime la factura fiscal

El sistema SHALL mostrar un overlay bloqueante ("Espere mientras se imprime su
factura...") en toda la app del Kiosko mientras `printKioskFiscalInvoice` está en
curso tras la confirmación, para que el cliente no vea la pantalla de
confirmación como si ya estuviera todo listo mientras la máquina fiscal sigue
imprimiendo en segundo plano.

#### Scenario: Impresión en curso al llegar a la confirmación

- **GIVEN** una orden del Kiosko recién registrada y facturada, sin
  `mf_invoice_number`, con la máquina fiscal conectada
- **WHEN** `confirmationPage` dispara `printKioskFiscalInvoice`
- **THEN** el overlay se muestra desde que empieza la impresión hasta que
  `printKioskFiscalInvoice` resuelve (éxito o fallo), sin bloquear la
  navegación a la pantalla de confirmación en sí
