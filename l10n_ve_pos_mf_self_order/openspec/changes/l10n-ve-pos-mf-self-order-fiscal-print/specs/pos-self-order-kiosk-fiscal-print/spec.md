# Spec delta: pos-self-order-kiosk-fiscal-print

## ADDED Requirements

### Requirement: El Kiosko imprime la factura fiscal en local al confirmar

El sistema SHALL imprimir la factura fiscal de la orden del Kiosko en la máquina
fiscal (TFHKA, Web Serial) desde el cliente del navegador, reutilizando el driver
(`window.fiscalPrinter`) y la lógica de armado de comandos de `l10n_ve_pos_mf`,
sin depender de una llamada al servidor Odoo para imprimir.

#### Scenario: Orden pagada y confirmada en el Kiosko

- **GIVEN** una caja en modo Kiosko con `l10n_ve_pos_mf_self_order` instalado y
  la máquina fiscal conectada y pareada por Web Serial
- **WHEN** el pago de una orden se aprueba y la orden se confirma
- **THEN** se imprime la factura fiscal en la máquina, y `mf_invoice_number`,
  `fiscal_machine` y `mf_reportz` quedan guardados en la orden

#### Scenario: Las líneas de pago del comprobante se toman del pago aprobado

- **GIVEN** que en el Kiosko el pago se registra en el servidor y la orden del
  cliente no tiene `payment_ids` al momento de imprimir
- **WHEN** se arma el payload fiscal
- **THEN** las `payment_lines` del comprobante se construyen a partir del método
  de pago aprobado y su monto (pasados explícitamente), con
  `code_fiscal_printer` como código de la forma de pago

### Requirement: La impresión fiscal no depende del servidor (imprimir-primero)

El sistema SHALL imprimir la factura fiscal ANTES e independientemente del RPC de
registro de la orden al servidor, de modo que un fallo o indisponibilidad del
servidor Odoo no impida ni pierda la impresión de una orden ya pagada.

#### Scenario: Servidor Odoo no accesible tras aprobar el pago

- **GIVEN** una orden del Kiosko cuyo pago fue aprobado, con el servidor Odoo
  temporalmente no accesible
- **WHEN** el cliente finaliza la orden
- **THEN** la factura fiscal se imprime igual, la orden se encola localmente para
  sincronizar, y el flujo avanza a la pantalla de confirmación sin bloquearse

#### Scenario: Sincronización diferida al volver la conexión

- **GIVEN** una orden del Kiosko impresa fiscalmente y encolada localmente porque
  el RPC de registro falló
- **WHEN** el servidor Odoo vuelve a estar accesible
- **THEN** la orden se sincroniza automáticamente, el servidor registra el pago y
  genera el `account.move`, y el `mf_invoice_number` impreso queda estampado en
  ese asiento (`_prepare_invoice_vals`)

### Requirement: La impresión fiscal del Kiosko es idempotente

El sistema SHALL evitar reimprimir o volver a cobrar una orden del Kiosko cuando
la finalización se reintenta.

#### Scenario: Reintento de una orden ya impresa

- **GIVEN** una orden del Kiosko que ya tiene `mf_invoice_number`
- **WHEN** el flujo de finalización se reintenta (p. ej. tras un fallo de red del
  RPC de registro)
- **THEN** no se emite un segundo comprobante fiscal ni se recobra la tarjeta; se
  reintenta solo el registro de la orden

### Requirement: Reimpresión de facturas fiscales fallidas por modo debug

El sistema SHALL permitir reenviar a la máquina fiscal una factura cuya impresión
falló, sin volver a cobrar, mediante una acción disponible en modo debug.

#### Scenario: Impresión fiscal fallida

- **GIVEN** una orden del Kiosko cuyo pago se aprobó pero cuya impresión fiscal
  falló
- **WHEN** ocurre el fallo
- **THEN** el payload fiscal ya armado se persiste localmente marcado como
  "pendiente de imprimir", sin recobrar la tarjeta

#### Scenario: Reenvío manual desde modo debug

- **GIVEN** una factura fiscal pendiente de imprimir y la máquina fiscal
  conectada
- **WHEN** el operador activa el modo debug y ejecuta la acción de reimpresión
- **THEN** el comprobante se reenvía a la máquina (`printInvoice(payload)`) y, si
  imprime, se guarda su `mf_invoice_number` en la orden

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
