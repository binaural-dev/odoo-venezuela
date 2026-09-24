# Spec delta: pos-self-order-kiosk-invoicing

## ADDED Requirements

### Requirement: Toda orden del Kiosko se marca para facturar

El sistema SHALL forzar `to_invoice=True` en toda orden creada desde una caja
en modo Kiosko (`self_ordering_mode == 'kiosk'`), sin depender de que el
cliente del Kiosko lo envíe, replicando la regla SENIAT que `l10n_ve_pos` ya
aplica en la caja normal.

#### Scenario: El cliente del Kiosko no envía `to_invoice`

- **GIVEN** una caja en modo Kiosko con `l10n_ve_pos_self_order` instalado
- **WHEN** el servidor recibe una orden del Kiosko cuyo payload no trae
  `to_invoice` (o lo trae en `False`)
- **THEN** la orden se persiste con `to_invoice=True`

#### Scenario: El modo Autopedido móvil (mobile) no se fuerza a facturar

- **GIVEN** una caja en `self_ordering_mode == 'mobile'` (QR de mesa), sin
  garantía de `partner_id` identificado
- **WHEN** el servidor recibe una orden de ese flujo
- **THEN** `to_invoice` NO se fuerza — se respeta el comportamiento nativo, para
  no facturar contra el consumidor genérico

### Requirement: La orden del Kiosko se factura al completarse el pago

El sistema SHALL generar la factura fiscal de la orden del Kiosko al
completarse el pago aprobado, ejecutando la finalización completa del core
(`_process_saved_order`: pagada + picking + costo + factura), no solo el cambio
de estado a `paid`.

#### Scenario: Pago aprobado en el Kiosko (Megasoft) genera factura

- **GIVEN** una orden del Kiosko en estado `draft` con `to_invoice=True` y un
  método de pago Megasoft de tarjeta-presente
- **WHEN** el pago se aprueba y `_payment_request_from_kiosk` registra el pago
- **THEN** la orden queda con un `account_move` posteado a nombre del
  `partner_id` identificado, y las líneas del asiento de pago llevan
  `foreign_debit`/`foreign_credit` derivados del `foreign_amount` del pago

#### Scenario: El asiento de pago refleja el monto en moneda foránea

- **GIVEN** un pago Megasoft registrado con `foreign_amount` = total foráneo de
  la orden y `foreign_rate` = tasa de la orden
- **WHEN** se generan los asientos de pago de la factura
  (`_create_payment_moves`)
- **THEN** cada línea del asiento lleva `foreign_debit = |foreign_amount|` en el
  lado deudor y `foreign_credit = |foreign_amount|` en el acreedor, con
  `foreign_rate`/`foreign_inverse_rate` = la tasa del pago

### Requirement: La finalización del pago del Kiosko es idempotente

El sistema SHALL evitar duplicar el pago o la factura si la finalización del
pago del Kiosko se reintenta (p. ej. si se perdió la respuesta de red), pese a
que el controlador de Kiosko del core reabre la orden a `draft` en cada
llamada.

#### Scenario: Reintento antes de facturar

- **GIVEN** una orden del Kiosko con la línea de pago ya registrada pero sin
  `account_move` (la finalización falló tras registrar el pago), reabierta a
  `draft` por `process_order`
- **WHEN** el cliente reintenta el registro del pago
- **THEN** no se registra un segundo pago (línea de pago existente) y la
  finalización se completa generando la factura

#### Scenario: Reintento después de facturar

- **GIVEN** una orden del Kiosko ya facturada (`account_move` posteado) cuya
  respuesta se perdió, reabierta a `draft` por `process_order`
- **WHEN** el cliente reintenta el registro del pago
- **THEN** no se genera una segunda factura, no se registra un segundo pago, y
  el estado final de la orden se restaura (`done`/`paid`)
