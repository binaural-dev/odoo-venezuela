## ADDED Requirements

### Requirement: Cuentas transitorias distintas en los dos diarios del cruce

Un método de pago (`pos.payment.method`) en moneda alterna (`is_foreign_currency`) o con moneda de cobro (`tender_currency_id`) NO DEBE (MUST NOT) quedar con su diario (`journal_id`) y su diario afectado (`cross_journal`) en la misma cuenta transitoria (`suspense_account_id`), ni al guardar el método ni al cambiar la transitoria de uno de sus diarios.

#### Scenario: Misma transitoria al guardar el método

- **WHEN** se guarda un método en moneda alterna cuyo diario y diario afectado tienen la misma cuenta transitoria, por ejemplo la que Odoo pone por defecto a todos los diarios de la compañía
- **THEN** se rechaza con un error de validación que nombra los dos diarios, el método y la cuenta, y pide una cuenta transitoria para cada diario

#### Scenario: Método con moneda de cobro

- **WHEN** se guarda un método con moneda de cobro (p. ej. EUR) cuyo diario transitorio y cuya caja real en EUR tienen la misma cuenta transitoria
- **THEN** se rechaza con el mismo error

#### Scenario: Misma transitoria al editar el diario

- **WHEN** en el diario afectado de un método en moneda alterna se pone la cuenta transitoria que ya tiene el diario del método, o al revés
- **THEN** se rechaza al guardar el diario, con el mismo error

#### Scenario: Transitorias distintas

- **WHEN** el diario y el diario afectado de un método en moneda alterna tienen cada uno su cuenta transitoria
- **THEN** el método y los diarios se guardan

#### Scenario: Configuración incompleta

- **WHEN** un método en moneda alterna no tiene diario afectado, o su diario no tiene cuenta transitoria
- **THEN** se guarda: esa configuración incompleta la reporta la apertura de la sesión

#### Scenario: Método sin cruce

- **WHEN** un método que no es de moneda alterna ni tiene moneda de cobro tiene un diario afectado con la misma cuenta transitoria que su diario
- **THEN** se guarda: ese método no hace cruce

#### Scenario: Método guardado antes de la regla

- **WHEN** un método en moneda alterna quedó guardado con las dos transitorias iguales antes de esta regla y no se edita
- **THEN** se sigue usando, y el cruce de su venta en efectivo se crea sin efecto contable
- **AND** si se le cambia un diario, la moneda alterna o la moneda de cobro, se rechaza hasta separar las transitorias

### Requirement: Diario del método en la moneda de sus cajas al guardar el método

Un método de pago (`pos.payment.method`) NO DEBE (MUST NOT) guardarse con un diario cuya moneda es distinta de la moneda de alguna de sus cajas (`config_ids`). Un diario sin moneda DEBE (MUST) aceptarse, porque trabaja en la moneda de la compañía. Es la regla del core (`pos.config._check_currencies`), que hasta ahora solo se revisaba al guardar la caja o al abrir la sesión. Un método sin caja DEBE (MUST) guardarse con un diario en cualquier moneda.

#### Scenario: Diario en otra moneda que la caja

- **WHEN** a un método de una caja en Bs se le pone un diario en USD
- **THEN** se rechaza al guardar el método, con un error que nombra el diario, el método, la caja y las dos monedas
- **AND** ya no hace falta abrir la caja para ver el error

#### Scenario: Caja agregada desde el método

- **WHEN** desde el formulario del método se le agrega una caja en Bs a un método con diario en USD
- **THEN** se rechaza con el mismo error

#### Scenario: Diario en la moneda de la caja

- **WHEN** el diario del método está en la moneda de cada una de sus cajas, también un método con moneda de cobro en EUR con su diario transitorio en USD en una caja en USD (`binaural_pos_multicurrency`)
- **THEN** se guarda

#### Scenario: Diario sin moneda

- **WHEN** el diario del método no tiene moneda
- **THEN** se guarda en cualquier caja: en una caja en la moneda de la compañía es el cobro en esa moneda, y en una caja en otra moneda (`binaural_pos_multicurrency`) también

#### Scenario: Método sin caja

- **WHEN** se guarda un método sin caja con un diario en cualquier moneda, también uno en moneda alterna o con moneda de cobro
- **THEN** se guarda, y se valida cuando se le agregue una caja, desde el método o desde la caja
