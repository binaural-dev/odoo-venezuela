## MODIFIED Requirements

### Requirement: Línea de extracto del cruce en el diario real

Por cada línea de un cruce sobre la Cuenta transitoria del `cross_journal` el sistema DEBE (MUST) crear en ese diario una línea de extracto con el mismo monto en la moneda del diario, la misma alterna, el mismo socio, la fecha del cruce y su `ref` como etiqueta, y DEBE (MUST) conciliarla enseguida contra su línea del cruce, uno a uno, cuando esa transitoria permite conciliación y las dos suman cero en la moneda de la compañía; si no, la DEBE (MUST) dejar sin conciliar y sin error. NO DEBE (MUST NOT) crearla si esa transitoria es también la del diario del método.

#### Scenario: Salida de efectivo cruzada

- **WHEN** se cruza una salida de 70 $ del cajón a un `cross_journal` en USD con su propia Cuenta transitoria conciliable
- **THEN** el `cross_journal` tiene una línea de extracto de +70 $ con la etiqueta del cruce, conciliada contra la línea del cruce
- **AND** la Cuenta transitoria del `cross_journal` queda sin saldo ni partidas abiertas

#### Scenario: Entrada y salida en la misma sesión

- **WHEN** se cruzan una entrada de 50 $ y una salida de 70 $
- **THEN** el `cross_journal` tiene dos líneas de extracto, −50 $ y +70 $, una por cruce

#### Scenario: Cruce combinado con entradas y salidas

- **WHEN** un cruce combinado tiene una pata de entradas y otra de salidas en la transitoria del `cross_journal`
- **THEN** se crea una línea de extracto por pata y cada una se concilia contra la suya

#### Scenario: Transitoria sin conciliación

- **WHEN** la Cuenta transitoria del `cross_journal` no permite conciliación
- **THEN** la línea de extracto se crea sin conciliar y el cruce no falla

#### Scenario: Cruce a otra tasa

- **WHEN** el cruce va a una tasa distinta de la del día de la línea de extracto y no suman cero en la moneda de la compañía
- **THEN** la línea de extracto queda sin conciliar, para conciliarla a mano (Odoo crea la diferencia en cambio)

#### Scenario: Línea del cruce ya conciliada

- **WHEN** la línea del cruce ya está conciliada
- **THEN** no se vuelve a conciliar y la línea de extracto queda abierta

#### Scenario: Transitorias compartidas

- **WHEN** el diario del método y el `cross_journal` tienen la misma Cuenta transitoria
- **THEN** el cruce se crea y no se crea ninguna línea de extracto
