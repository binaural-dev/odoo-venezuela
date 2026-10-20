# Spec delta: outstanding-credits-widget

## ADDED Requirements

### Requirement: El cruce desde el widget aplica el monto mostrado

Al asignar un crédito pendiente desde el widget, cuando la moneda del pago
difiere de la de la factura, el crédito aplicado (en moneda de la factura) SHALL
ser el monto que mostró el widget para esa línea, calculado con la tasa sin
redondear del widget (`rate`), para cualquier combinación de monedas y de
decimales.

#### Scenario: Pago en VEF anterior a la factura en USD

- **GIVEN** un pago en VEF anterior a la factura (el widget valora a la fecha de la factura)
- **WHEN** se asigna desde el widget
- **THEN** lo aplicado SHALL igualar lo mostrado

#### Scenario: Pago en USD contra factura en VEF

- **WHEN** se asigna un pago en USD a una factura en VEF
- **THEN** lo aplicado SHALL igualar lo mostrado; si el pago excede la factura, la factura SHALL quedar saldada y el resto del pago disponible

#### Scenario: Pago en una tercera moneda

- **GIVEN** una factura en USD y un pago en EUR (moneda de compañía VEF)
- **WHEN** se asigna desde el widget
- **THEN** lo aplicado SHALL igualar lo mostrado y la línea del pago SHALL consumirse en EUR y en Bs de forma consistente

#### Scenario: Tercera moneda con consumo parcial del pago

- **GIVEN** un pago en EUR que vale más que la factura en USD
- **WHEN** se asigna desde el widget
- **THEN** la factura SHALL quedar saldada y al pago SHALL sobrarle la parte proporcional en EUR y en Bs

#### Scenario: Monedas con distinto número de decimales

- **WHEN** el pago está en una moneda de 0 decimales (JPY) o de 3 (KWD)
- **THEN** lo aplicado SHALL igualar lo mostrado y el residual en divisa de la línea SHALL quedar en cero

#### Scenario: Factura de proveedor y facturas con varias cuotas

- **WHEN** el documento es una factura de proveedor, o tiene varias cuotas por cobrar/pagar
- **THEN** lo aplicado SHALL igualar lo mostrado (con varias cuotas, con diferencias de céntimos por el redondeo de cada parcial)

#### Scenario: Cruces de retenciones y ND de IGTF

- **WHEN** el cruce es de una retención (`l10n_ve_exchange_is_retention_reconcile`) o salda la ND de IGTF contra el remanente de su pago
- **THEN** SHALL conservar la tasa nativa/contable del pago y SHALL NOT ajustarse al widget

### Requirement: `compute_bi_igtf` admite facturas con varias cuotas

El cálculo de la base imponible de IGTF SHALL considerar todas las líneas por
cobrar/pagar de la factura al buscar los parciales de cada pago, sin asumir una
sola.

#### Scenario: Factura con dos cuotas pagada

- **GIVEN** una factura con dos cuotas por cobrar
- **WHEN** se paga (incluso con un diario IGTF o en modo ND de IGTF)
- **THEN** `bi_igtf` SHALL calcularse sin error

### Requirement: Quitar el IGTF no toca los asientos sin línea de IGTF

`remove_igtf_from_account_move` SHALL devolver `False` sin modificar el asiento
del pago cuando este no tiene línea de IGTF y no es un movimiento de
reaplicación de anticipos, de modo que el desconciliado normal del parcial
pedido sea el único efecto.

#### Scenario: Pago sin IGTF aplicado a dos facturas

- **GIVEN** un pago en USD (o en VEF) sin línea de IGTF que salda dos facturas
- **WHEN** se desconcilia una de ellas
- **THEN** el pago SHALL permanecer publicado, la otra factura SHALL seguir pagada y SHALL quedar un solo parcial

#### Scenario: Pago con línea de IGTF

- **WHEN** el asiento tiene línea de IGTF
- **THEN** SHALL seguir el flujo existente (borrador, absorción del IGTF en la línea de CxC/CxP y nueva publicación)

### Requirement: El widget valora a la fecha de la factura; la conciliación manual conserva la valoración nativa

Para un pago en moneda de la compañía anterior a una factura en divisa, el widget SHALL
valorar el pago con la tasa de la fecha de la factura y el cruce SHALL aplicar ese monto, aunque
la factura quede parcialmente abierta. La conciliación manual desde apuntes SHALL conservar la
valoración nativa de Odoo (tasa de la fecha del pago); este cambio no la modifica.

#### Scenario: Tasas que suben, pago de 3.600 Bs del 01-01 (36) contra factura de $100 del 01-08 (40)

- **WHEN** se asigna desde el widget
- **THEN** SHALL mostrarse y aplicarse $90, la factura SHALL quedar parcial con $10 (400 Bs) pendientes y SHALL NOT emitirse nota
- **AND** la conciliación manual de las mismas líneas SHALL aplicar $100, dejar la factura pagada y emitir una NC de 400 Bs

#### Scenario: Tasas que suben, pago de 4.000 Bs del 01-01 (36) contra factura de $100 del 01-08 (40)

- **WHEN** se asigna desde el widget
- **THEN** SHALL mostrarse y aplicarse $100, el pago SHALL quedar consumido y SHALL NOT emitirse nota
- **AND** la conciliación manual SHALL dejar 400 Bs sin aplicar en el pago y emitir una NC de 400 Bs

### Requirement: Desconciliar nunca cancela el asiento origen del pago

`account.payment.advanced_move_ids` SHALL devolver solo asientos de cruce de
anticipo publicados. Al desconciliar, el asiento ORIGEN del pago SHALL NOT
cancelarse; solo se cancela el asiento de CRUCE cuando es su parcial el que se rompe.

#### Scenario: Pago con un cruce de anticipo sin publicar

- **GIVEN** un pago que salda una factura y tiene ligado un asiento de cruce en borrador
- **WHEN** se desconcilia el parcial del propio pago
- **THEN** el asiento del pago SHALL seguir publicado y el parcial SHALL desconciliarse normalmente

#### Scenario: Pago con un cruce de anticipo publicado

- **WHEN** se desconcilia el parcial del propio pago
- **THEN** SHALL abrirse el wizard de confirmación sin cancelar ni desconciliar nada todavía

#### Scenario: Se rompe el parcial del asiento de cruce

- **WHEN** se desconcilia la factura del asiento de cruce
- **THEN** SHALL cancelarse solo ese cruce y el pago SHALL seguir publicado

### Requirement: El cruce de anticipo solo se deshace por sus caminos gestionados

Un asiento de cruce de anticipo (`is_advance_move`) SHALL NOT pasar a borrador ni cancelarse
con sus botones propios, y SHALL NOT publicarse sin pago origen. Solo SHALL deshacerse al
desconciliar desde la factura o al pasar a borrador o cancelar su pago origen.

#### Scenario: Botones propios del cruce

- **WHEN** se intenta pasar a borrador o cancelar un cruce de anticipo publicado
- **THEN** SHALL fallar con un error y el cruce SHALL seguir publicado

#### Scenario: Cruce cancelado al desconciliar

- **WHEN** se desconcilia el cruce desde la factura
- **THEN** SHALL quedar cancelado y desligado del pago, y SHALL NOT poder volver a borrador ni publicarse sin pago origen

#### Scenario: Cruce en borrador al cancelar el pago origen

- **GIVEN** un cruce en borrador ligado al pago
- **WHEN** se cancela o pasa a borrador el pago
- **THEN** el cruce SHALL cancelarse y desligarse del pago sin abrir el wizard

#### Scenario: Cruce huérfano al desconciliar

- **GIVEN** un cruce de anticipo publicado sin pago origen (con o sin línea de IGTF)
- **WHEN** se desconcilia desde la factura
- **THEN** SHALL cancelarse, SHALL NOT quedar atrapado contra la guarda de publicación, y la factura SHALL quedar sin ese pago

#### Scenario: Borrador que no es cruce de anticipo

- **GIVEN** un asiento en borrador que apunta al pago por `origin_payment_advanced_payment_id` pero sin `is_advance_move`
- **WHEN** se cancela el pago
- **THEN** el asiento SHALL NOT cancelarse ni desligarse
