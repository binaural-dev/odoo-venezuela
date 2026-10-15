# Spec delta: l10n_ve_accountant (ticket 15726)

## ADDED Requirements

### Requirement: Los asientos de diferencial alterno no vuelven a borrador

Un asiento con `l10n_ve_exchange_foreign_diff_entry` (nativo con montos alternos
o standalone) SHALL NOT poder volver a borrador, igual que el asiento de
diferencial nativo de Odoo. Extra no pedido en el ticket, detectado al probar:
el asiento lo genera la conciliación y su ciclo de vida lo gobierna ella; romper
la conciliación lo revierte automáticamente, y esa es la vía de corrección.

#### Scenario: Asiento alterno vigente

- **GIVEN** un asiento de diferencial alterno enlazado como `partial.exchange_move_id`
- **WHEN** se intenta pasar a borrador
- **THEN** el sistema SHALL lanzar un error (ya bloqueado por el core)

#### Scenario: Asiento alterno revertido al romper la conciliación

- **GIVEN** un asiento alterno cuya conciliación se deshizo (quedó revertido)
- **WHEN** se intenta pasar a borrador el asiento o su reverso
- **THEN** el sistema SHALL lanzar un error y SHALL NOT cambiar el estado

### Requirement: El asiento alterno aparece en los apuntes conciliados de toda la cadena

`open_reconcile_view` SHALL incluir el asiento standalone en los apuntes
conciliados de cada documento de la cadena (factura, pago, asiento nativo) y
también al abrirse desde el propio asiento standalone, que nunca concilia.

#### Scenario: Abrir los apuntes conciliados desde la factura

- **GIVEN** una factura pagada con diferencial alterno standalone
- **WHEN** se abren sus apuntes conciliados desde la factura, el pago o el asiento nativo
- **THEN** el asiento alterno SHALL aparecer en los tres casos

### Requirement: El default del toggle no se valida al crear ni durante la carga del plan

`l10n_ve_use_foreign_exchange_diff` SHALL ser `True` por defecto. Solo una
activación explícita SHALL exigir diario y cuentas de cambio. El valor por
defecto SHALL NOT validarse al crear la compañía ni mientras se carga un plan de
cuentas; al terminar `_load`, si faltan diario o cuentas, el toggle SHALL
apagarse con un warning (nunca dejar la compañía con el toggle en `True` y sin
configuración).

#### Scenario: Activación explícita sin configuración

- **GIVEN** una compañía sin diario ni cuentas de cambio (con o sin plan)
- **WHEN** se crea con el toggle en `True`, o se pasa de `False` a `True`
- **THEN** el sistema SHALL lanzar un error indicando qué configurar

#### Scenario: Compañía nueva con el default

- **WHEN** se crea una compañía sin indicar el toggle
- **THEN** el toggle SHALL quedar en `True` y la creación SHALL NOT fallar

#### Scenario: Plan que no configura el diferencial

- **GIVEN** un plan de cuentas que no deja diario ni cuentas de cambio
- **WHEN** termina la carga del plan
- **THEN** el toggle SHALL quedar en `False` y SHALL registrarse un warning

### Requirement: `foreign_balance` queda alineado con débito/crédito alterno

Tras redistribuir el residuo alterno, `foreign_balance` SHALL ser igual a
`foreign_debit - foreign_credit` en las líneas reescritas. Es un fix hacia
adelante: NO hay migración; los datos ya existentes no se modifican y, si se
reporta alguno desfasado, se corrige manualmente.

#### Scenario: Factura nueva con redistribución del residuo

- **GIVEN** una factura cuyo residuo alterno se redistribuye (p. ej. débito alterno 25,90)
- **WHEN** se postea
- **THEN** el saldo alterno SHALL ser 25,90 (igual a débito menos crédito)

### Requirement: El wizard de pagos rechaza importe 0.0 y oculta "Pago indexado" fuera de "A convenir"

El wizard SHALL rechazar un importe 0.0 comparado con el redondeo de la
moneda del wizard. El check "Pago indexado" SHALL ser visible solo con el modo
de indexación "A convenir".
