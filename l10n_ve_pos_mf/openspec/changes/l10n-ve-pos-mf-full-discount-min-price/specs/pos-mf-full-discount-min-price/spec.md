## ADDED Requirements

### Requirement: Sustitución de líneas con descuento del 100% por el mínimo fiscal

El sistema SHALL sustituir por el mínimo fiscal (precio unitario 0,01 y
descuento 0) toda línea de una orden de PdV con máquina fiscal cuyo neto
quedaría en 0,00 por un descuento del 100% (de línea o global) y cuyo precio
base sea mayor que 0, aplicándolo al momento de aplicar el descuento y, como
respaldo, antes de pasar a la pantalla de pago. El precio original SHALL
guardarse para poder restaurarlo. El sistema NO SHALL modificar la validación
_check_max_discount ni ningún módulo fuera de l10n_ve_pos_mf.

#### Scenario: Descuento por línea del 100%

- **GIVEN** una orden con un producto de precio > 0 en una caja con máquina
  fiscal
- **WHEN** el cajero aplica un descuento del 100% a esa línea
- **THEN** la línea pasa a precio 0,01 sin descuento, el total refleja 0,01, la
  máquina fiscal imprime la línea y la factura generada lleva `discount = 0`
  (no la bloquea `_check_max_discount`)

#### Scenario: Descuento global del 100%

- **GIVEN** una orden con una o varias líneas de precio > 0
- **WHEN** el cajero aplica un descuento global del 100%
- **THEN** cada línea afectada pasa a precio 0,01 sin descuento, con el mismo
  resultado en total, impresión fiscal y factura

#### Scenario: Reversión al cambiar o quitar el descuento

- **GIVEN** una línea que fue sustituida por 0,01 tras un descuento del 100%
- **WHEN** se cambia el descuento a un valor menor a 100% o se quita
- **THEN** se restaura el precio original de la línea antes de aplicar el nuevo
  descuento, quedando como si nunca se hubiera sustituido

#### Scenario: Inferencia del descuento global sobre el precio real

- **GIVEN** líneas previamente sustituidas por 0,01
- **WHEN** se vuelve a aplicar/recalcular el descuento global
- **THEN** la inferencia del porcentaje usa el precio real (restaurado), no
  0,01

#### Scenario: Descuento parcial sin cambios

- **WHEN** se aplica un descuento menor al 100% (el neto queda > 0)
- **THEN** la línea conserva su precio y su descuento tal cual (comportamiento
  idéntico al actual)
