## ADDED Requirements

### Requirement: Línea con descuento del 100% facturada en el mínimo fiscal 0,01

El sistema SHALL facturar en el mínimo fiscal 0,01 la LÍNEA COMPLETA (subtotal
0,01, no 0,01 por unidad) de una orden de PdV con máquina fiscal cuando un
descuento (de línea o global) del 100% dejaría su neto en 0,00 y su precio base
sea mayor que 0, conservando la cantidad. Para lograrlo con precios de 2
decimales el sistema SHALL fijar precio unitario 0,01 y descuento
(1 − 1/cantidad) × 100 con cantidad mayor que 1, precio 0,01 sin descuento con
cantidad entre 0,5 y 1, y con cantidad menor que 0,5 el precio igual a
0,01 / cantidad redondeado hacia arriba al céntimo, sin descuento; en todos los
casos el subtotal queda en 0,01, con el descuento por debajo de 100% (no lo
bloquea `_check_max_discount`) y el precio unitario mayor que 0. El sistema
SHALL recalcular precio y descuento si cambia la cantidad, y SHALL guardar el
precio original para poder restaurarlo. El sistema SHALL reconocer estas líneas
también por sus datos (precio 0,01 con el descuento que corresponde a su
cantidad, o devolución de una línea así), para que sigan tratándose igual tras
recargar la caja o al reimprimir un pedido pendiente. Como la máquina fiscal
arma cada línea como precio × cantidad con 2 decimales y no puede repartir 0,01
entre N unidades con el precio, el sistema SHALL enviar estas líneas a la
máquina fiscal con su cantidad entera N a 0,01 y un descuento por monto sobre el
ítem de (N − 1) × 0,01, y con cantidad fraccionaria como 1 × 0,01 con la
cantidad real en la descripción. El sistema NO SHALL modificar la validación
`_check_max_discount`.

#### Scenario: Descuento por línea del 100% con cantidad grande

- **GIVEN** una línea con 50 unidades de un producto de precio > 0 en una caja
  con máquina fiscal
- **WHEN** el cajero aplica un descuento del 100% a esa línea
- **THEN** el subtotal de la línea queda en 0,01 (no 0,50), la cantidad sigue en
  50, la factura no se bloquea (descuento < 100%) y la máquina fiscal recibe esa
  línea como 50 × 0,01 con un descuento de 0,49 sobre el ítem (neto 0,01)

#### Scenario: Descuento global del 100%

- **GIVEN** una orden con una o varias líneas de precio > 0
- **WHEN** el cajero aplica un descuento global del 100%
- **THEN** cada línea afectada queda con subtotal 0,01 conservando su cantidad,
  con el mismo resultado en factura e impresión fiscal

#### Scenario: Cambio de cantidad tras la sustitución

- **GIVEN** una línea ya facturada en el mínimo fiscal (subtotal 0,01)
- **WHEN** se cambia la cantidad de esa línea
- **THEN** el descuento se recalcula para que el subtotal siga en 0,01 con la
  nueva cantidad

#### Scenario: Reversión al cambiar o quitar el descuento

- **GIVEN** una línea facturada en el mínimo fiscal tras un descuento del 100%
- **WHEN** se cambia el descuento a un valor menor a 100% o se quita
- **THEN** se restaura el precio original de la línea antes de aplicar el nuevo
  descuento, quedando como si nunca se hubiera sustituido

#### Scenario: Cambio del descuento global tras un global del 100%

- **GIVEN** una orden con A = 100 y B = 50 × 2 con descuento global del 100%
  (líneas en el mínimo fiscal)
- **WHEN** el cajero teclea un descuento global del 50%
- **THEN** se restauran los precios reales y se aplica el 50% tecleado (A = 50,
  B = 25 × 2), no un porcentaje deducido del monto de `pos_discount`

#### Scenario: Producto pesado de menos de 0,5 kg

- **GIVEN** una línea de 0,300 kg de un producto de precio > 0
- **WHEN** el cajero aplica un descuento del 100%
- **THEN** la línea queda con precio 0,04 sin descuento y subtotal 0,01 (no
  0,00), y la MF la recibe como 1 × 0,01 con `CANT 0,3 KG -` en la descripción

#### Scenario: Pedido pendiente u orden recargada

- **GIVEN** una orden con una línea de 3 unidades en el mínimo fiscal (precio
  0,01, descuento 66,67%) que se recargó del servidor o se imprime desde
  "Imprimir pedido pendiente"
- **WHEN** se imprime en la MF
- **THEN** la línea se reconoce por sus datos y se envía como 3 × 0,01 con
  `q-` 0,02, igual que en la sesión original

#### Scenario: Nota de crédito de una línea en el mínimo fiscal

- **GIVEN** una orden facturada con una línea de 2 o más unidades en el mínimo
  fiscal (precio 0,01 con descuento)
- **WHEN** se devuelve esa línea y se imprime la nota de crédito
- **THEN** la línea de la devolución conserva el precio 0,01 y el descuento de
  la original, y la MF la recibe con su cantidad y un descuento por monto que la
  deja en 0,01, igual que en Odoo

#### Scenario: Cantidad fraccionaria en el mínimo fiscal

- **GIVEN** un producto pesado con 1,25 kg facturado en el mínimo fiscal
- **WHEN** se imprime la factura fiscal
- **THEN** la MF recibe la línea como 1 × 0,01 con la descripción
  `CANT 1,25 KG - <producto>`

#### Scenario: Monto informativo del descuento global sobre el precio real

- **GIVEN** una orden con 3 líneas de 2 unidades cada una y precio > 0
- **WHEN** el cajero aplica un descuento global del 100% y se imprime la factura
  fiscal
- **THEN** la línea informativa `DESC. GLOBAL` muestra el total real de las
  líneas (precio real × cantidad), no Σ 0,01 × cantidad (0,06)

#### Scenario: Descuento parcial sin cambios

- **WHEN** se aplica un descuento menor al 100% (el neto queda > 0)
- **THEN** la línea conserva su precio y su descuento tal cual (comportamiento
  idéntico al actual)
