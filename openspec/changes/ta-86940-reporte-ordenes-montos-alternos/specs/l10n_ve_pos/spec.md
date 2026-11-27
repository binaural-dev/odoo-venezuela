## ADDED Requirements

### Requirement: Análisis de órdenes del PdV con montos en moneda alterna

El análisis de órdenes del Punto de Venta (`report.pos.order`) DEBE (MUST) mostrar, por cada
línea de pedido, la moneda alterna de la compañía (`foreign_currency_id`), el subtotal sin
impuestos en esa moneda (`foreign_untaxed_total`) y el total con impuestos
(`foreign_total_billed`), como medidas de las vistas pivot y gráfico.

Los montos DEBEN (MUST) calcularse con los montos de la línea en la moneda de la compañía por la
tasa congelada del pedido (`foreign_currency_rate`, moneda alterna por unidad de la moneda de la
compañía), redondeados a los decimales de la moneda alterna. NO DEBEN (MUST NOT) depender de
`foreign_subtotal` ni `foreign_total` de la línea. El signo DEBE (MUST) seguir la regla de
`price_total` del core, de modo que los reembolsos resten.

Un pedido sin `foreign_currency_rate` DEBE (MUST) aparecer en el análisis con sus montos en la
moneda de la compañía y 0 en la moneda alterna: es el comportamiento esperado, no hay tasa con
qué convertir.

#### Scenario: Venta

- **WHEN** se vende en el PdV una línea de 4.000 Bs sin impuestos y 4.640 Bs con impuestos, en un
  pedido con tasa 40 Bs/$
- **THEN** el análisis de órdenes muestra 100 $ de subtotal y 116 $ de total para esa línea, en la
  moneda alterna de la compañía

#### Scenario: Pedido sin tasa

- **WHEN** un pedido no tiene `foreign_currency_rate`
- **THEN** sus líneas aparecen en el análisis con los montos en Bs y 0 en la moneda alterna

### Requirement: Reembolsos valorados a la tasa de la venta original en el análisis de órdenes

En una línea de reembolso (con `refunded_orderline_id`), `report.pos.order` DEBE (MUST) calcular
los montos en moneda alterna con la tasa del pedido de la venta original, igual que el PdV y
`pos.order._get_payment_foreign_rate` valoran los reembolsos. Solo si la venta original no tiene
tasa DEBE (MUST) usar la del pedido de reembolso.

#### Scenario: Reembolso a otra tasa

- **WHEN** una venta de 4.000 Bs + 640 Bs de impuesto se hace a 40 Bs/$ y se reembolsa entera otro
  día a 50 Bs/$
- **THEN** la línea de reembolso resta 100 $ de subtotal y 116 $ de total (no 80 $ ni 92,80 $), y
  la suma en $ de la venta y el reembolso es 0, igual que la factura y su nota de crédito

#### Scenario: Reembolso parcial a la misma tasa

- **WHEN** se reembolsa 1 de 2 unidades de una venta, con la misma tasa
- **THEN** el reembolso resta la mitad en $ y el neto de la venta y el reembolso es la otra mitad

### Requirement: Etiquetas de las medidas en moneda alterna

Las vistas pivot y gráfico de `report.pos.order` DEBEN (MUST) etiquetar las medidas como
«Subtotal <moneda>» y «Total <moneda>», con el nombre de la moneda alterna de la compañía activa.

Limitación conocida: si se filtran varias compañías con monedas alternas distintas, la medida
suma montos de monedas distintas y la etiqueta muestra solo la moneda de la compañía activa.

#### Scenario: Compañía con USD como moneda alterna

- **WHEN** un usuario de una compañía con USD como moneda alterna abre el análisis de órdenes en
  pivot o gráfico
- **THEN** las medidas se llaman «Subtotal USD» y «Total USD»

#### Scenario: Compañía sin moneda alterna

- **WHEN** la compañía activa no tiene `foreign_currency_id`
- **THEN** las vistas no cambian las etiquetas de las medidas
