## ADDED Requirements

### Requirement: Línea con descuento del 100% facturada en el mínimo fiscal 0,01

El sistema SHALL facturar en el mínimo fiscal 0,01 la LÍNEA COMPLETA (subtotal
0,01, no 0,01 por unidad) de una orden de PdV con máquina fiscal cuando un
descuento (de línea o global) del 100% dejaría su neto en 0,00 y su precio base
sea mayor que 0, conservando la cantidad. Para lograrlo con precios de 2
decimales el sistema SHALL fijar precio unitario 0,01 y descuento
(1 − 1/cantidad) × 100, de modo que el subtotal quede en 0,01 con el descuento
por debajo de 100% (no lo bloquea `_check_max_discount`) y el precio unitario
mayor que 0. El sistema SHALL recalcular ese descuento si cambia la cantidad, y
SHALL guardar el precio original para poder restaurarlo. Como la máquina fiscal
arma cada línea como precio × cantidad con 2 decimales y no puede repartir 0,01
entre N unidades, el sistema SHALL enviar estas líneas a la máquina fiscal como
1 × 0,01. El sistema NO SHALL modificar la validación `_check_max_discount` ni
ningún módulo fuera de l10n_ve_pos_mf.

#### Scenario: Descuento por línea del 100% con cantidad grande

- **GIVEN** una línea con 50 unidades de un producto de precio > 0 en una caja
  con máquina fiscal
- **WHEN** el cajero aplica un descuento del 100% a esa línea
- **THEN** el subtotal de la línea queda en 0,01 (no 0,50), la cantidad sigue en
  50, la factura no se bloquea (descuento < 100%) y la máquina fiscal recibe esa
  línea como 1 × 0,01

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

#### Scenario: Inferencia del descuento global sobre el precio real

- **GIVEN** líneas previamente facturadas en el mínimo fiscal
- **WHEN** se vuelve a aplicar/recalcular el descuento global
- **THEN** la inferencia del porcentaje usa el precio real (restaurado), no 0,01

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
