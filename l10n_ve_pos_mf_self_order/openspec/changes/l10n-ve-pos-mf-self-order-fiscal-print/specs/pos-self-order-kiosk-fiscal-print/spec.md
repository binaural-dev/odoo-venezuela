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
- **THEN** la orden NO se imprime (no hay orden en Odoo), se encola para reintento
  automático del registro, y la impresión queda pendiente hasta que la orden se
  registre

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
