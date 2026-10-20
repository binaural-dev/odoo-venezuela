# Spec delta: pos-self-order-kiosk-payment-summary

## ADDED Requirements

### Requirement: Resumen de montos del Kiosko antes de pagar

El Kiosko SHALL mostrar, ANTES de que el cliente pulse Pagar, en la pantalla
del carrito (`pos_self_order.CartPage`, en lugar del "Total/Taxes" del core) o,
en modo solo escaneo/búsqueda, debajo del resumen de líneas de
`ProductListPage` (ese modo se salta el carrito),
un resumen con: base imponible, desglose de impuestos por tasa (una fila por
cada `account.tax.group` presente en la orden — IVA 16%, 8%, exento, lo que
aplique) y el total en la moneda local (Bs.). Cuando la compañía tenga una
moneda foránea configurada (`res.company.foreign_currency_id`) SHALL mostrar
también el total en esa moneda, calculado con la MISMA tasa operativa que usa
`pos.order.recompute_prices` (server-side, `l10n_ve_pos_self_order/models/pos_order.py`)
para fijar `foreign_amount_total` en la orden ya pagada — así el monto que el
cliente ve antes de pagar coincide con el que termina en la factura.

El resumen NO SHALL ir en la pantalla de pago: con un único método de pago
(la configuración recomendada, un solo método Megasoft cuyo VPOS deja elegir
tarjeta/pago móvil/transferencia) el core lo auto-selecciona al montar
`PaymentPage` y el VPOS abre de inmediato, sin que se pueda leer nada. Ese
salto directo al VPOS SHALL conservarse.

#### Scenario: Base, impuestos y total en Bs.

- **GIVEN** una orden del Kiosko con líneas gravadas a distintas tasas
- **WHEN** el cliente revisa su orden antes de pagar
- **THEN** ve la base imponible, una fila por cada tasa de impuesto presente
  y el total en Bs.

#### Scenario: Total en moneda foránea

- **GIVEN** una compañía con `foreign_currency_id` configurada
- **WHEN** el cliente revisa su orden antes de pagar
- **THEN** ve también el total en esa moneda, rotulado "Total <código de la
  moneda>" (p. ej. "Total USD", "Total EUR" según `foreign_currency_id`),
  calculado con los mismos
  helpers de `l10n_ve_pos` que usa la caja (`get_foreign_total_with_tax`,
  tasa operativa de `pos.config` y redondeo de la moneda), y ese monto coincide con el
  `foreign_amount_total` que termina en la factura de la orden

#### Scenario: Sin moneda foránea configurada

- **GIVEN** una compañía sin `foreign_currency_id`
- **WHEN** el cliente revisa su orden antes de pagar
- **THEN** no se muestra la fila de total en moneda foránea

#### Scenario: Un solo método Megasoft

- **GIVEN** el Kiosko con un único método de pago Megasoft
- **WHEN** el cliente pulsa Pagar tras ver el resumen
- **THEN** el VPOS abre directamente, sin pantalla intermedia
