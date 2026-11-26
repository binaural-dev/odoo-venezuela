## MODIFIED Requirements

### Requirement: Ajuste de balances en pagos del wizard sin IGTF

Para un pago creado desde el wizard (`payment_from_wizard`) cuyo `igtf_amount` es cero o negativo, `_prepare_move_line_default_vals` DEBE (MUST) forzar la cuadratura contra el residual real de las facturas origen. Cuando el pago trae líneas de write-off y el asiento tiene al menos tres líneas, `_fix_writeoff_balance` fija el balance de la contrapartida (`vals[1]`) en el negativo del residual firmado de las facturas origen (`-amount_residual_signed`), recalcula su `amount_currency` desde ese balance y absorbe la diferencia en la línea de write-off (`vals[2]`), solo si el pago cubre la deuda (ver abajo); cuando no hay write-off, todas las facturas origen tienen la misma fecha de documento y esa fecha coincide con la del pago, fija los balances de las dos primeras líneas en ±`amount_residual_signed` según el `payment_type` (liquidez positiva y contrapartida negativa en pagos `inbound`; al revés en `outbound`), de modo que el balance conserve el signo de `amount_currency` también al pagar notas de crédito.

Un pago del mismo día de la factura «cubre la deuda» (`_same_date_payment_covers_residual`) cuando sus Bs. igualan el residual dentro de 0,10 Bs. (en el caso con write-off, dentro del redondeo de la moneda de la compañía), o cuando el monto del pago iguala el residual en la moneda del pago dentro de una unidad de redondeo de esa moneda. Con fechas distintas entre la factura y el pago, o con un pago parcial o excedente, NO se fuerza: se conserva el diferencial cambiario real.

#### Scenario: Pago con write-off sin IGTF

- **WHEN** se crea desde el wizard un pago sin IGTF con línea de write-off cuyo balance de contrapartida difiere del residual de la factura, y el pago cubre la deuda
- **THEN** la contrapartida queda por el residual en moneda de la compañía y el write-off absorbe la diferencia

#### Scenario: Pago exacto en la fecha de la factura

- **WHEN** un pago sin IGTF ni write-off cancela una única factura cuya fecha de documento es la del pago y cubre la deuda
- **THEN** los balances de liquidez y contrapartida se fijan en el residual de la factura con los signos correspondientes al tipo de pago

#### Scenario: Pago en otra moneda con IVA redondeado por línea

- **GIVEN** una factura de USD 1.000,00 cuyas líneas redondeadas (862,07 más IVA 16 %) suman Bs. 1,03 más que USD 1.000,00 por la tasa
- **WHEN** se paga el mismo día en USD o en Bs. desde el wizard
- **THEN** los Bs. del pago son los de la factura, la factura queda pagada y no nace NC, ND ni asiento de diferencial

#### Scenario: Fechas distintas

- **WHEN** la factura es del 25/09 y el pago del 28/09 en otra moneda
- **THEN** los Bs. del pago no se igualan a los de la factura y el diferencial cambiario real se genera

### Requirement: Línea contable de IGTF en el asiento del pago

Al generar las líneas del pago (`_prepare_move_line_default_vals`), un pago creado desde el wizard (`payment_from_wizard`) con `igtf_percentage` distinto de cero e `igtf_amount` mayor que cero DEBE (MUST) agregar una línea "IGTF" contra la cuenta IGTF de la compañía (`customer_account_igtf_id` o `supplier_account_igtf_id` según `partner_type`, con error si no está configurada), ajustando la contrapartida por cobrar/pagar para separar la porción del impuesto y recalculando la línea de write-off cuando existe; la línea no se genera cuando alguna factura origen pertenece al diario de compra internacional, ni en flujos con contexto `from_pos`, ni cuando las líneas ya incluyen una sobre la cuenta de anticipo del partner.

Cuando el pago cubre la deuda el mismo día de la factura, el balance de la contrapartida DEBE (MUST) ser el residual de las facturas del pago (`base_residual`), no la suma de todas las facturas origen (`total_base_residual`), y el write-off DEBE (MUST) quedar en las mismas unidades del balance: en un pago saliente, el monto en divisa de la línea de IGTF se SUMA al total sin write-off (igual que su balance), no se resta.

#### Scenario: Pago de cliente con IGTF

- **WHEN** se crea desde el wizard un pago entrante con IGTF calculado
- **THEN** el asiento del pago incluye una línea "IGTF" al crédito por la porción del impuesto contra la cuenta IGTF de clientes

#### Scenario: Cuenta IGTF sin configurar

- **WHEN** se genera la línea de IGTF sin cuenta IGTF configurada en la compañía
- **THEN** se lanza un error pidiendo asignarla en los ajustes

#### Scenario: Factura de importación

- **WHEN** las facturas origen del pago pertenecen a un diario de compra internacional
- **THEN** el asiento del pago no incluye línea de IGTF

#### Scenario: Pago con IGTF y write-off (COM/VEN-C04x y C05x)

- **WHEN** se paga desde el wizard, en un diario IGTF de otra moneda, una factura con una diferencia mínima conciliada contra una cuenta de ajuste
- **THEN** el write-off es la diferencia mínima y la factura queda pagada (ventas C04x: Bs. 1.343,36 y no Bs. 856.005,86; C05x: Bs. 5.595,59 y no Bs. 1.831.906,77; compras C04x: Bs. 4.252,23 y no Bs. 975.900,91)

### Requirement: Base imponible del IGTF acumulada en la factura

`compute_bi_igtf` de `account.move` DEBE (MUST) mantener por factura: `igtf_top_aply` (tope = `amount_total_signed` por el porcentaje, menos el porcentaje de IGTF de los importes conciliados por pagos sin línea de IGTF), `bi_igtf` (base imponible acumulada de los pagos con IGTF conciliados, limitada a `amount_total_signed`), `alter_bi_igtf` (IGTF acumulado aplicado) y `foreign_bi_igtf` (base convertida a la moneda del documento, limitada a `amount_total`), recorriendo los asientos de pago conciliados y sus conciliaciones parciales, derivados directamente de `matched_debit_ids`/`matched_credit_ids` sobre las líneas conciliables y resueltos con `.sudo()` (ver el requisito vigente sobre el acceso a pagos de otra compañía).

El cálculo DEBE (MUST) ejecutarse cuando `_igtf_base_is_computable` es verdadero: la factura tiene saldo abierto (`amount_residual` distinto de cero), o está publicada (`state == 'posted'`), no está revertida (`payment_state != 'reversed'`) y tiene conciliaciones en sus líneas conciliables. En cualquier otro caso los cuatro campos quedan en cero. El cálculo NO DEBE (MUST NOT) decidirse con `payment_state` como compuerta de entrada: es otro campo almacenado cuyo orden de recálculo respecto de `bi_igtf` varía entre procesos; con el saldo en cero y `payment_state` aún en `not_paid`, la base y el tope quedaban en cero y, como `bi_igtf` depende solo de `amount_residual`, no se recalculaban (`test12_payment_from_invoice_with_igtf_journal_desconciliation` fallaba según la corrida).

#### Scenario: Factura pagada con IGTF

- **WHEN** una factura tiene un pago conciliado cuyo asiento contiene línea de IGTF
- **THEN** `bi_igtf` acumula la base del pago, `alter_bi_igtf` acumula el IGTF y ninguno supera los topes de la factura

#### Scenario: Pago sin IGTF

- **WHEN** el pago conciliado no tiene línea de IGTF
- **THEN** el tope `igtf_top_aply` se reduce en el porcentaje de IGTF del importe conciliado por ese pago

#### Scenario: Documento sin residual y sin pagos

- **WHEN** el documento tiene residual cero, no tiene conciliaciones o está en borrador
- **THEN** `igtf_top_aply`, `bi_igtf`, `alter_bi_igtf` y `foreign_bi_igtf` quedan en cero

#### Scenario: Factura pagada con `payment_state` desactualizado

- **WHEN** se recalcula la base de una factura publicada, con saldo cero y conciliada, cuyo `payment_state` aún figura `not_paid`
- **THEN** la base y el tope se calculan igual que con `payment_state` `paid`, en cualquier orden de recálculo

#### Scenario: Factura revertida

- **WHEN** la factura tiene `payment_state` `reversed`
- **THEN** los cuatro campos quedan en cero

#### Scenario: Pago conciliado en una compañía sin acceso de lectura para el usuario actual

- **GIVEN** una factura conciliada contra un pago cuyo asiento vive en una compañía a la que el usuario actual no tiene acceso de lectura
- **WHEN** se recomputa `compute_bi_igtf` para esa factura
- **THEN** el cálculo se completa sin `AccessError`, incluyendo ese pago en la base imponible

**Nota sobre la decisión de no recalcular facturas cerradas:** se mantiene la decisión vigente (sin migración): los campos se recalculan cuando la factura vuelve a tocarse. La nota anterior que describía `payment_state` como una simplificación sin escenario conocido queda sustituida por esta compuerta: sí había un escenario (el orden de recálculo entre procesos) y se corrige quitando `payment_state` de la compuerta.
