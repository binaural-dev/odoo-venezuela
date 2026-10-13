# pos-refund-original-rate Specification

## Purpose
TBD - created by archiving change l10n-ve-pos-refund-exact-rate-snap. Update Purpose after archive.
## Requirements
### Requirement: El ajuste a la deuda del reembolso a tasa exacta se decide en la divisa tecleada

En un reembolso con tasa exacta, el sistema SHALL ajustar la línea a la deuda
local exacta cuando el monto foráneo tecleado esté a un paso de redondeo de la
divisa o menos de la deuda en divisa mostrada (deuda local × 1 / tasa exacta,
redondeada a la divisa), comparando con la precisión de la divisa. En otro caso
SHALL espejar lo tecleado (|foráneo| × tasa exacta) con el signo del reembolso.
El resultado MUST NOT depender del ruido de coma flotante.

#### Scenario: Límite de un céntimo por arriba

- **GIVEN** un reembolso con deuda −3.600 Bs y tasa exacta 40 (90,00 $)
- **WHEN** el cajero teclea 90,01 $
- **THEN** la línea queda en −3.600 Bs

#### Scenario: Límite de un céntimo por abajo y dos céntimos

- **GIVEN** el mismo reembolso
- **WHEN** el cajero teclea 89,99 $ o 89,98 $
- **THEN** la línea queda en −3.600 Bs con 89,99 y en −3.599,20 Bs con 89,98

#### Scenario: Deuda que no cae en el céntimo

- **GIVEN** un reembolso con deuda −3.600,25 Bs y tasa exacta 40 (90,00625 $,
  mostrada 90,01 $)
- **WHEN** el cajero teclea 90,02 $ o 89,99 $
- **THEN** la línea queda en −3.600,25 Bs con 90,02 y en −3.599,60 Bs con 89,99

#### Scenario: Tasa no entera

- **GIVEN** un reembolso con deuda −3.285 Bs y tasa exacta 36,5 (90 $)
- **WHEN** el cajero teclea 90,01 $ o 90,02 $
- **THEN** la línea queda en −3.285 Bs con 90,01 y en −3.285,73 Bs con 90,02

