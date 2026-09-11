# Spec delta: igtf-note-debit

## ADDED Requirements

### Requirement: El modo `debit_note` es 100% opt-in por compañía

El sistema MUST comportarse de forma idéntica a `l10n_ve_igtf` sin este
módulo instalado cuando `company.igtf_note_debit_mode == "inline"`. Todos los
métodos sobrescritos (`compute_bi_igtf`, `remove_igtf_from_account_move`,
`js_assign_outstanding_line`, `_create_advance_payment_move`,
`_create_igtf_moves_in_payments`) MUST delegar directo en `super()` para las
compañías en modo `inline`, sin duplicar ni alterar la lógica de la base.

#### Scenario: Compañía en modo inline no ve ningún cambio

- **GIVEN** una compañía con `igtf_note_debit_mode = "inline"`
- **WHEN** se registra un pago con IGTF aplicable sobre una factura
- **THEN** el IGTF se contabiliza como línea embebida en el mismo asiento de pago, igual que sin este módulo instalado
- **AND** no se genera ninguna Nota de Débito

#### Scenario: Cambiar a modo debit_note requiere el producto de percepción configurado

- **GIVEN** una compañía sin `igtf_note_debit_product_id` configurado
- **WHEN** se intenta guardar `igtf_note_debit_mode = "debit_note"`
- **THEN** se lanza `UserError` pidiendo configurar el producto en Ajustes > Contabilidad > IGTF

### Requirement: Checkbox "Incluir IGTF en el pago" en el wizard de registro de pago

Con el modo `debit_note` activo, el wizard `account.payment.register` MUST
exponer el checkbox `igtf_note_debit_include_in_payment` (valor por defecto:
`company.igtf_note_debit_include_in_payment_default`), que determina si el
pago que se registra cubre factura + IGTF juntos, o solo la factura.

#### Scenario: Checkbox marcado -- el pago cubre factura + IGTF

- **GIVEN** una factura con IGTF aplicable (journal `is_igtf`) y la compañía en modo `debit_note`
- **AND** el checkbox "Incluir IGTF en el pago" está marcado
- **WHEN** se registra el pago
- **THEN** el monto del pago incluye el importe de la factura más el IGTF calculado
- **AND** se genera la Nota de Débito por el monto exacto del IGTF

#### Scenario: Checkbox desmarcado -- el pago solo cubre la factura

- **GIVEN** la misma factura, con el checkbox desmarcado
- **WHEN** se registra el pago
- **THEN** el monto del pago cubre solo el importe de la factura
- **AND** el wizard muestra el desglose "Importe + IGTF = Total a pagar"

### Requirement: Generación y conciliación de la Nota de Débito

Al confirmar un pago que aplica IGTF con la compañía en modo `debit_note`, el
sistema MUST generar automáticamente una Nota de Débito
(`prepare_igtf_payment_debit_note`) vinculada a la factura de origen y al
pago (`origin_payment_to_pay_igtf`), marcada con
`l10n_ve_igtf_note_debit_origin = True`, usando el producto de percepción
configurado como única línea.

La ND SHOULD conciliarse de una de dos formas, según el checkbox "Incluir
IGTF en el pago":

- **Marcado**: contra el remanente del MISMO pago
  (`settle_igtf_debit_note` → `js_assign_outstanding_line`).
- **Desmarcado**: contra un SEGUNDO pago independiente, forzado en VEF
  (`_settle_igtf_debit_note_with_vef_payment`), usando
  `company.igtf_note_debit_vef_journal_id` o el primer diario banco/caja en
  VEF no marcado como IGTF, si no está configurado.

#### Scenario: ND conciliada contra el remanente del mismo pago

- **GIVEN** un pago que cubre factura + IGTF (checkbox marcado)
- **WHEN** se postea el pago
- **THEN** la ND queda conciliada contra el residual del mismo asiento de pago
- **AND** el `payment_state` de la ND queda en `paid`

#### Scenario: ND conciliada con un pago aparte en VEF

- **GIVEN** un pago que cubre solo la factura (checkbox desmarcado)
- **WHEN** se postea el pago
- **THEN** se crea y postea un `account.payment` aparte, en VEF, por el monto exacto de la ND
- **AND** se concilia contra la ND

#### Scenario: Sin diario VEF configurado ni detectable

- **GIVEN** ninguna compañía tiene `igtf_note_debit_vef_journal_id` configurado ni un diario banco/caja VEF no-IGTF disponible
- **WHEN** se intenta saldar la ND con un pago aparte
- **THEN** se lanza `UserError` pidiendo configurar el diario

### Requirement: Reversa por desconciliación o cancelación del pago de origen

Si el pago que originó una ND se desconcilia o se cancela -- incluyendo
`action_cancel` directo sin pasar por "Fijar a Borrador" -- el sistema MUST
generar automáticamente una Nota de Crédito en Forma Libre
(`create_note_credit_igtf`) que reversa la ND, tanto para ventas
(`out_invoice`) como para compras (`in_invoice`).

#### Scenario: Desconciliar el pago de una factura de venta con ND

- **GIVEN** una factura de venta con una ND de IGTF posteada y conciliada
- **WHEN** se rompe la conciliación del pago de origen
- **THEN** se genera y postea automáticamente una Nota de Crédito que revierte la ND

#### Scenario: Cancelar directamente el pago de origen de una factura de compra

- **GIVEN** una factura de compra con una ND de IGTF posteada y conciliada
- **WHEN** se cancela el pago de origen directamente (`action_cancel`, sin fijar a borrador antes)
- **THEN** se genera igual la Nota de Crédito de reversa

### Requirement: Cálculo de la base imponible y el IGTF aplicado en la factura

`compute_bi_igtf` MUST alimentar, en la factura, los campos `bi_igtf` (base
imponible en moneda de compañía), `foreign_bi_igtf` (la misma base en moneda
de la factura), `alter_bi_igtf` (monto de IGTF efectivamente cobrado) e
`igtf_top_aply` (tope de IGTF = base × alícuota), reconociendo tanto el flujo
`inline` como el flujo `debit_note`.

`bi_igtf` MUST NOT re-convertirse a la tasa de cambio del pago -- SHALL tomar
el monto ya asentado por la conciliación, que refleja la tasa con la que la
factura quedó contabilizada. El diferencial cambiario entre la tasa de la
factura y la del pago es responsabilidad de `l10n_ve_exchange_difference`,
no de este módulo.

#### Scenario: Factura pagada con ND de IGTF muestra base e IGTF correctos

- **GIVEN** una factura con IGTF pagada íntegramente vía Nota de Débito (modo `debit_note`)
- **WHEN** se recomputa `compute_bi_igtf`
- **THEN** `bi_igtf`, `foreign_bi_igtf`, `alter_bi_igtf` e `igtf_top_aply` quedan con los valores correctos
- **AND** `alter_bi_igtf` coincide con el total de la ND

#### Scenario: Factura sin ningún pago con IGTF

- **GIVEN** una factura sin pagos aplicados o sin IGTF aplicable
- **WHEN** se recomputa `compute_bi_igtf`
- **THEN** los cuatro campos quedan en cero

### Requirement: Respeto de `indexed_default` en el cálculo del IGTF

El sistema MUST usar la tasa de cambio del PAGO cuando
`company.indexed_default` (ligado a `indexaxion_payment_mode`, de
`l10n_ve_accountant`) está activo, y la tasa de cambio de la FACTURA cuando
está desactivado, tanto para calcular el monto de IGTF (delegado en
`l10n_ve_igtf`) como para convertirlo a moneda de compañía al armar la ND
(`wizard/account_payment_register.py::_create_payments`). Ambos pasos MUST
usar la MISMA fecha de conversión.

#### Scenario: Compañía no indexada -- se usa la tasa de la factura

- **GIVEN** una compañía con `indexed_default = False`
- **AND** una factura contabilizada a una tasa distinta de la vigente el día del pago
- **WHEN** se registra el pago y se genera la ND de IGTF
- **THEN** el monto de IGTF se calcula con la tasa de cambio del día de la FACTURA
- **AND** la conversión a moneda de compañía de ese mismo monto usa la MISMA fecha (la de la factura), no la del pago

#### Scenario: Compañía indexada -- se usa la tasa del pago

- **GIVEN** una compañía con `indexed_default = True` (comportamiento por defecto)
- **WHEN** se registra el pago y se genera la ND de IGTF
- **THEN** el monto de IGTF se calcula y convierte con la tasa de cambio del día del PAGO

### Requirement: Bloqueo de pagos agrupados multi-factura en modo `debit_note`

El sistema MUST impedir registrar un pago agrupado (`group_payment`) que
cubra más de una factura pagada a través de un diario IGTF cuando la
compañía está en modo `debit_note` -- cada factura debe generar su propia
ND, y un solo pago agrupado no puede repartirse limpiamente entre varias.

#### Scenario: Intentar agrupar el pago de dos facturas con IGTF

- **GIVEN** dos facturas con IGTF aplicable de la misma compañía en modo `debit_note`
- **WHEN** el usuario intenta registrar un único pago agrupado (`group_payment = True`) para ambas
- **THEN** se lanza `UserError` explícito pidiendo desmarcar "Agrupar Pagos" y registrar el pago de cada factura por separado
