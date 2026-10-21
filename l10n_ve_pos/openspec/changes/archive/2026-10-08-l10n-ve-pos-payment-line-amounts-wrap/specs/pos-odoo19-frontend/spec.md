## ADDED Requirements

### Requirement: Los montos de una línea de pago se muestran completos

El PdV SHALL mostrar completos los montos de una línea de pago (el de la moneda
del método y, si lo hay, el de la otra moneda): MUST NOT truncarlos. Si no caben
junto al nombre del método, SHALL pasarlos a una segunda fila; lo que puede
truncarse es el nombre.

#### Scenario: Método foráneo en la caja VES

- **GIVEN** la caja VES con la tasa a 803,34
- **WHEN** el cajero cobra 70 $ con Efectivo USD (Caja VES)
- **THEN** la línea muestra "$ 70,00 / 56.233,80 Bs.F" completo, no "$ 70,00 / 56.2…"

#### Scenario: Par de montos que no cabe en una fila

- **GIVEN** una línea de pago con montos tan largos que el par no cabe en el ancho de la columna
- **WHEN** se muestra la pantalla de pago
- **THEN** el par se parte por el " / " y los dos montos se ven completos

#### Scenario: Línea que cabe en una fila

- **GIVEN** una línea de pago cuyo nombre y montos caben en el ancho de la columna
- **WHEN** se muestra la pantalla de pago
- **THEN** la línea sigue en una sola fila
