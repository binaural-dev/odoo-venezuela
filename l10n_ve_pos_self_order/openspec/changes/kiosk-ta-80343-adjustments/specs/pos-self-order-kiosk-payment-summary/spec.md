# Spec delta: pos-self-order-kiosk-payment-summary

## ADDED Requirements

### Requirement: Resumen de montos en la pantalla de pago del Kiosko

La pantalla de pago del Kiosko (`pos_self_order.PaymentPage`) SHALL mostrar
un resumen con: base imponible, desglose de impuestos por tasa (una fila por
cada `account.tax.group` presente en la orden — IVA 16%, 8%, exento, lo que
aplique) y el total en la moneda local (Bs.). Cuando la compañía tenga una
moneda foránea configurada (`res.company.foreign_currency_id`) SHALL mostrar
también el total en esa moneda, calculado con la MISMA tasa operativa que usa
`pos.order.recompute_prices` (server-side, `l10n_ve_pos_self_order/models/pos_order.py`)
para fijar `foreign_amount_total` en la orden ya pagada — así el monto que el
cliente ve antes de pagar coincide con el que termina en la factura.

La implementación SHALL heredar el template del core
(`t-inherit-mode="extension"`) sin reemplazarlo, y SHALL seguir siendo
compatible con el `patch()` (solo JS, sin plantilla) que
`binaural_megasoft_self_order` aplica sobre el mismo componente.

#### Scenario: Base, impuestos y total en Bs.

- **GIVEN** una orden del Kiosko con líneas gravadas a distintas tasas
- **WHEN** el cliente llega a la pantalla de pago
- **THEN** ve la base imponible, una fila por cada tasa de impuesto presente
  y el total en Bs.

#### Scenario: Total en moneda foránea

- **GIVEN** una compañía con `foreign_currency_id` configurada
- **WHEN** el cliente llega a la pantalla de pago del Kiosko
- **THEN** ve también el total en esa moneda, calculado con los mismos
  helpers de `l10n_ve_pos` que usa la caja (`get_foreign_total_with_tax`,
  tasa operativa de `pos.config` y redondeo de la moneda), y ese monto coincide con el
  `foreign_amount_total` que termina en la factura de la orden

#### Scenario: Sin moneda foránea configurada

- **GIVEN** una compañía sin `foreign_currency_id`
- **WHEN** el cliente llega a la pantalla de pago del Kiosko
- **THEN** no se muestra la fila de total en moneda foránea

#### Scenario: Compatible con el patch de Megasoft

- **GIVEN** `binaural_megasoft_self_order` instalado (patch JS de
  `PaymentPage`, sin plantilla propia)
- **WHEN** el Kiosko carga la pantalla de pago
- **THEN** el resumen de montos y el flujo de cobro de Megasoft conviven sin
  conflicto (el `t-inherit` no reemplaza nodos que ese patch necesite)
