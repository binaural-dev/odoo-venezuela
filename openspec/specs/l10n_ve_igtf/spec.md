# l10n_ve_igtf

## Purpose

Gestiona los pagos anticipados (cuentas puente de anticipo de clientes y proveedores, widget de anticipos en factura, cruces de anticipo) y la aplicación del Impuesto a las Grandes Transacciones Financieras (IGTF, 3% por defecto) en pagos y facturas, incluyendo su columna en los libros fiscales. Extiende `account.move`, `account.move.line`, `account.payment`, `account.payment.register`, `account.tax`, `account.account`, `account.journal`, `res.partner`, `res.company` y `wizard.accounting.reports`, y define el modelo abstracto `l10n_ve_igtf.utils` y el wizard `move.action.cancel.advance.payment.wizard`. Depende de `l10n_ve_accountant` (moneda alterna, `taxpayer_type`), `l10n_ve_invoice` (libros fiscales, forma libre), `l10n_ve_tax_payer` y `l10n_ve_base`.

## Requirements

### Requirement: Cuentas de anticipo restringidas por tipo

Una cuenta contable con `is_advance_account` activo DEBE (MUST) ser de tipo `asset_current` o `liability_current` (onchange `_onchange_is_advance_account` de `account.account`), y las cuentas de anticipo por defecto de la compañía (`advance_customer_account_id`, `advance_supplier_account_id`) DEBEN (MUST) estar marcadas como cuenta de anticipo (onchange `_onchange_default_igtf_account` de `res.company`, que no valida cuando el contexto trae `install_mode` o `skip_check`).

#### Scenario: Marcar una cuenta por cobrar como anticipo

- **WHEN** se marca `is_advance_account` en una cuenta cuyo tipo no es activo o pasivo corriente
- **THEN** se lanza un error indicando los tipos permitidos

#### Scenario: Cuenta por defecto sin marca

- **WHEN** se configura como cuenta de anticipo de la compañía una cuenta sin `is_advance_account`
- **THEN** se lanza un error de validación

### Requirement: Cuenta destino de los pagos anticipados

Cuando un pago tiene `is_advance_payment` activo, `_compute_destination_account_id` DEBE (MUST) asignar como cuenta destino la cuenta de anticipo por defecto del partner: `default_advance_customer_account_id` para clientes y `default_advance_supplier_account_id` para proveedores (campos de `res.partner` inicializados desde las cuentas por defecto de la compañía).

#### Scenario: Anticipo de cliente

- **WHEN** se marca un pago de cliente como anticipo y el partner tiene cuenta de anticipo de cliente
- **THEN** la cuenta destino del pago es esa cuenta de anticipo

### Requirement: Validación de la cuenta destino según el tipo de pago

El constraint `_check_advance_payment_account` de `account.payment` DEBE (MUST) exigir: en anticipos de proveedor una cuenta `asset_current` con `is_advance_account`; en anticipos de cliente una cuenta `liability_current` con `is_advance_account`; y en pagos estándar prohibir cuentas de anticipo y exigir tipos `asset_receivable` o `liability_payable`. La validación se omite cuando el pago no tiene cuenta destino y cuando el contexto trae `install_mode` o `skip_check`, y el error se lanza como `UserError`.

#### Scenario: Anticipo de cliente con cuenta incorrecta

- **WHEN** un pago anticipado de cliente usa una cuenta que no es pasivo corriente de anticipo
- **THEN** se lanza un error indicando el tipo de cuenta requerido

#### Scenario: Pago estándar con cuenta de anticipo

- **WHEN** un pago sin marca de anticipo usa una cuenta con `is_advance_account`
- **THEN** se lanza un error pidiendo desmarcar el anticipo o cambiar la cuenta

#### Scenario: Carga de datos con contexto de instalación

- **WHEN** se escribe un pago con `install_mode` o `skip_check` en el contexto
- **THEN** el constraint no valida la cuenta destino

### Requirement: Diarios IGTF con moneda extranjera obligatoria

Un diario con `is_igtf` activo DEBE (MUST) tener moneda asignada y distinta de VEF (onchange `_check_igtf_currency` de `account.journal`); además, en el formulario de pago, un diario IGTF DEBE (MUST) usarse solo en pagos anticipados y con una cuenta destino de anticipo (onchange `_onchange_journal_id` de `account.payment`).

#### Scenario: Diario IGTF en bolívares

- **WHEN** se marca `is_igtf` en un diario con moneda VEF o sin moneda
- **THEN** se lanza un error exigiendo una moneda extranjera

#### Scenario: Pago no anticipado con diario IGTF

- **WHEN** un pago sin `is_advance_payment` selecciona un diario IGTF
- **THEN** se lanza un error indicando que debe ser un pago anticipado

### Requirement: Aplicabilidad del IGTF según tipo de contribuyente

`_check_igtf_apply_improved` de `res.partner` DEBE (MUST) determinar si aplica IGTF: en documentos de venta (`out_invoice`/`out_refund`) aplica cuando la compañía es contribuyente `special` o `formal` y el partner tiene cuenta de anticipo de cliente; en documentos de compra (`in_invoice`/`in_refund`) aplica cuando el `taxpayer_type` del proveedor es `special` o `formal` y el partner tiene cuenta de anticipo de proveedor; en cualquier otro caso no aplica.

#### Scenario: Venta de compañía contribuyente especial

- **WHEN** se evalúa una factura de cliente y la compañía es contribuyente especial
- **THEN** el método devuelve verdadero si el partner tiene cuenta de anticipo de cliente

#### Scenario: Compra a proveedor ordinario

- **WHEN** se evalúa una factura de proveedor cuyo `taxpayer_type` es `ordinary`
- **THEN** el método devuelve falso y no se aplica IGTF

### Requirement: Porcentaje de IGTF configurable por compañía

La compañía DEBE (MUST) definir el porcentaje del IGTF en `igtf_percentage` (por defecto 3.00) junto con las cuentas de IGTF de cliente (`customer_account_igtf_id`, pasivo corriente) y de proveedor (`supplier_account_igtf_id`, gasto) y el diario de cruces `advance_payment_igtf_journal_id`, todos editables desde `res.config.settings`.

#### Scenario: Cambio del porcentaje

- **WHEN** un administrador cambia el porcentaje de IGTF en ajustes
- **THEN** los nuevos cálculos de IGTF usan ese porcentaje

### Requirement: Fórmula de cálculo del IGTF por pago

`calculate_igtf_for_payment` de `l10n_ve_igtf.utils` DEBE (MUST) calcular el IGTF como el mínimo entre el monto pagado y la deuda residual de la factura (ambos convertidos a moneda de la compañía a la fecha del pago, o a la fecha de la factura cuando el pago no es indexado, según el parámetro `indexed_default`) multiplicado por `igtf_percentage/100`, topado por el IGTF restante de la factura (`igtf_top_aply - alter_bi_igtf`); devuelve 0 cuando ese restante es exactamente cero, cuando el tope iguala el residual convertido (con IGTF no nulo) o cuando el IGTF calculado supera el tope, y convierte el resultado desde la moneda de la compañía a la moneda del pago salvo que se pida la base (`base=True`).

#### Scenario: Pago parcial en divisa

- **WHEN** se paga en divisa una porción de una factura sin IGTF previo
- **THEN** el IGTF es el monto pagado (convertido) por el porcentaje de la compañía, expresado en la moneda del pago

#### Scenario: Tope de IGTF consumido

- **WHEN** el IGTF acumulado de la factura (`alter_bi_igtf`) iguala exactamente el tope (`igtf_top_aply`)
- **THEN** el cálculo devuelve 0 y no se genera más IGTF

#### Scenario: Pago no indexado

- **WHEN** el cálculo se invoca con `indexed_default` falso
- **THEN** las conversiones a la moneda de la compañía usan la tasa de la fecha de la factura y no la del pago

### Requirement: Detección del IGTF en el wizard de pagos

El campo `is_igtf` del wizard `account.payment.register` DEBE (MUST) activarse solo cuando el diario del pago tiene `is_igtf`, el partner aplica IGTF según `_check_igtf_apply_improved`, la moneda del wizard no es VEF, la factura no es una nota de débito (`debit_origin_id`) y su diario no es de compra internacional.

#### Scenario: Pago en divisa a factura ordinaria

- **WHEN** se abre el wizard con diario IGTF sobre una factura de cliente aplicable en moneda distinta de VEF
- **THEN** `is_igtf` y `is_igtf_on_foreign_exchange` quedan activos

#### Scenario: Factura de compra internacional

- **WHEN** la factura pertenece al diario de compra internacional
- **THEN** `is_igtf` permanece falso aunque el diario del pago sea IGTF

### Requirement: El monto del wizard incluye el IGTF

Cuando `is_igtf` está activo, `_compute_amount` del wizard DEBE (MUST) fijar `amount` como el monto por defecto a pagar más el IGTF calculado, exponiendo el IGTF en `igtf_amount`/`igtf_to_show` y el monto sin IGTF en `amount_without_difference`; si el usuario edita el monto, el IGTF se recalcula sobre el monto introducido y la diferencia de pago (`payment_difference`) se calcula contra el monto efectivo (monto menos IGTF).

#### Scenario: Apertura del wizard con IGTF

- **WHEN** el wizard se abre con IGTF aplicable
- **THEN** `amount` es el residual por defecto más el IGTF y `amount_without_difference` es el residual sin IGTF

#### Scenario: Edición manual del monto

- **WHEN** el usuario cambia el monto del pago
- **THEN** el IGTF se recalcula sobre el nuevo monto y `payment_difference` compara el monto efectivo contra lo adeudado

### Requirement: Exclusión de diarios IGTF en la selección por defecto

`_compute_journal_id` y `_get_batch_journal` del wizard DEBEN (MUST) excluir los diarios con `is_igtf` al proponer el diario por defecto del pago, de modo que un diario IGTF solo se use por selección explícita del usuario.

#### Scenario: Apertura del wizard

- **WHEN** el wizard busca el diario por defecto
- **THEN** los diarios marcados `is_igtf` no se proponen automáticamente

### Requirement: Línea contable de IGTF en el asiento del pago

Al generar las líneas del pago (`_prepare_move_line_default_vals`), un pago creado desde el wizard (`payment_from_wizard`) con `igtf_percentage` distinto de cero e `igtf_amount` mayor que cero DEBE (MUST) agregar una línea "IGTF" contra la cuenta IGTF de la compañía (`customer_account_igtf_id` o `supplier_account_igtf_id` según `partner_type`, con error si no está configurada), ajustando la contrapartida por cobrar/pagar para separar la porción del impuesto y recalculando la línea de write-off cuando existe; la línea no se genera cuando alguna factura origen pertenece al diario de compra internacional, ni en flujos con contexto `from_pos`, ni cuando las líneas ya incluyen una sobre la cuenta de anticipo del partner.

#### Scenario: Pago de cliente con IGTF

- **WHEN** se crea desde el wizard un pago entrante con IGTF calculado
- **THEN** el asiento del pago incluye una línea "IGTF" al crédito por la porción del impuesto contra la cuenta IGTF de clientes

#### Scenario: Cuenta IGTF sin configurar

- **WHEN** se genera la línea de IGTF sin cuenta IGTF configurada en la compañía
- **THEN** se lanza un error pidiendo asignarla en los ajustes

#### Scenario: Factura de importación

- **WHEN** las facturas origen del pago pertenecen a un diario de compra internacional
- **THEN** el asiento del pago no incluye línea de IGTF

### Requirement: Ajuste de balances en pagos del wizard sin IGTF

Para un pago creado desde el wizard (`payment_from_wizard`) cuyo `igtf_amount` es cero o negativo, `_prepare_move_line_default_vals` DEBE (MUST) forzar la cuadratura contra el residual real de las facturas origen: cuando el pago trae líneas de write-off y el asiento tiene al menos tres líneas, `_fix_writeoff_balance` fija el balance de la contrapartida (`vals[1]`) en el negativo del residual firmado de las facturas origen (`-amount_residual_signed`), recalcula su `amount_currency` desde ese balance y absorbe la diferencia en la línea de write-off (`vals[2]`); cuando no hay write-off, y siempre que la diferencia entre ese residual y el balance de la línea de liquidez no supere 0,1, todas las facturas origen tengan la misma fecha de documento y esa fecha coincida con la del pago, fija los balances de las dos primeras líneas en ±`amount_residual_signed` según el `partner_type`.

#### Scenario: Pago con write-off sin IGTF

- **WHEN** se crea desde el wizard un pago sin IGTF con línea de write-off cuyo balance de contrapartida difiere del residual de la factura
- **THEN** la contrapartida queda por el residual en moneda de la compañía y el write-off absorbe la diferencia

#### Scenario: Pago exacto en la fecha de la factura

- **WHEN** un pago sin IGTF ni write-off cancela una única factura cuya fecha de documento es la del pago y la diferencia de conversión es menor o igual a 0,1
- **THEN** los balances de liquidez y contrapartida se fijan en el residual de la factura con los signos correspondientes al tipo de partner

### Requirement: Base imponible del IGTF acumulada en la factura

`compute_bi_igtf` de `account.move` DEBE (MUST) mantener por factura: `igtf_top_aply` (tope = `amount_total_signed` por el porcentaje, menos el porcentaje de IGTF de los importes conciliados por pagos sin línea de IGTF), `bi_igtf` (base imponible acumulada de los pagos con IGTF conciliados, limitada a `amount_total_signed`), `alter_bi_igtf` (IGTF acumulado aplicado) y `foreign_bi_igtf` (base convertida a la moneda del documento, limitada a `amount_total`), recorriendo los asientos de pago conciliados y sus conciliaciones parciales -- derivados directamente de `matched_debit_ids`/`matched_credit_ids` sobre las líneas conciliables (no del Many2many computado `reconciled_lines_ids`, que dispara el `Field.write()` completo al escribirse y puede producir `RecursionError` en cadenas de `super()` profundas, ver ticket 14119, PR #1163). El cálculo solo se ejecuta cuando el residual del documento es distinto de cero o su `payment_state` es `paid`/`in_payment`; en cualquier otro caso los cuatro campos quedan en cero.

Ese derivado DEBE (MUST) resolverse con `.sudo()` antes de leer las líneas del asiento de pago contraparte: a diferencia de `reconciled_lines_ids` (núcleo), que filtra sus contrapartes con `_filtered_access('read')` antes de devolverlas, `matched_debit_ids`/`matched_credit_ids` no aplica ese mismo filtro -- sin `.sudo()`, este compute ALMACENADO (`store=True`) lanzaría `AccessError` en cuanto el usuario actual no tenga permiso de lectura sobre la contraparte (ej. un pago en OTRA compañía), en vez de simplemente omitir esa línea como hacía el comportamiento anterior.

#### Scenario: Factura pagada con IGTF

- **WHEN** una factura tiene un pago conciliado cuyo asiento contiene línea de IGTF
- **THEN** `bi_igtf` acumula la base del pago, `alter_bi_igtf` acumula el IGTF y ninguno supera los topes de la factura

#### Scenario: Pago sin IGTF

- **WHEN** el pago conciliado no tiene línea de IGTF
- **THEN** el tope `igtf_top_aply` se reduce en el porcentaje de IGTF del importe conciliado por ese pago

#### Scenario: Documento sin residual y sin pagos

- **WHEN** el documento tiene residual cero y su `payment_state` no es `paid` ni `in_payment`
- **THEN** `igtf_top_aply`, `bi_igtf`, `alter_bi_igtf` y `foreign_bi_igtf` quedan en cero

#### Scenario: Pago conciliado en una compañía sin acceso de lectura para el usuario actual

- **GIVEN** una factura conciliada contra un pago cuyo asiento vive en una compañía a la que el usuario actual no tiene acceso de lectura
- **WHEN** se recomputa `compute_bi_igtf` para esa factura
- **THEN** el cálculo se completa sin `AccessError`, incluyendo ese pago en la base imponible

### Requirement: Bloque IGTF en el resumen de impuestos

`_get_tax_totals_summary` de `account.tax` DEBE (MUST) agregar al resumen la clave `igtf` con: `apply_igtf` (verdadero solo cuando `bi_igtf > 0`), `igtf_show` (verdadero cuando el importe es solo sugerido), el nombre con el porcentaje, y la base y el monto del IGTF en moneda del documento y de la compañía con sus formatos; cuando `bi_igtf` es cero la base usada es el total del documento, de modo que el bloque reporta un IGTF sugerido en lugar de cero. En la raíz del resumen (no dentro de `igtf`) DEBE (MUST) agregar `amount_total_igtf` / `foreign_amount_total_igtf` con sus versiones formateadas. Para `out_invoice` agrega además el bloque `igtf_free_form` con el IGTF calculado sobre el total de la factura y el flag `show_igtf_suggested_account_move` de la compañía, que se expone como dato del bloque y no condiciona su creación.

#### Scenario: Factura con IGTF aplicado

- **WHEN** una factura tiene `bi_igtf` mayor que cero
- **THEN** `tax_totals['igtf']` reporta `apply_igtf` verdadero con la base real acumulada y el monto del impuesto

#### Scenario: Factura de venta sin pagos

- **WHEN** la factura de cliente no tiene IGTF aplicado
- **THEN** `tax_totals['igtf']` reporta `apply_igtf` falso con la base igual al total de la factura y el bloque `igtf_free_form` sugiere el IGTF sobre ese total

### Requirement: Widget de anticipos pendientes en la factura

Las facturas publicadas con estado de pago `not_paid` o `partial` DEBEN (MUST) exponer en `invoice_outstanding_credits_debits_widget_advance_payment` las líneas no conciliadas del partner comercial cuyo saldo tenga el signo contrario al documento, buscadas sobre las cuentas por cobrar/pagar de la propia factura más las cuentas de anticipo del tipo que corresponde al `move_type` (`liability_current` para `out_invoice` e `in_refund`; `asset_current` para el resto), y conservando solo las líneas que están en una cuenta de anticipo o que llevan `payment_id_advance`, con el monto residual convertido a la moneda de la factura. El widget estándar de créditos pendientes DEBE (MUST) excluir las líneas de anticipo y los asientos de cruce (`is_advance_move`), y `invoice_has_outstanding` considera ambos widgets. La conversión respeta `keep_alter_value_vef` del pago: los pagos en VEF con la marca se convierten desde `amount_residual` a la fecha del pago (revalorización), y sin la marca desde `amount_residual_currency` a la fecha mayor entre factura y pago; cuando la línea ya está en la moneda de la factura se usa `amount_residual_currency` sin conversión.

#### Scenario: Factura con anticipo disponible

- **WHEN** el partner tiene un anticipo publicado sin conciliar y la factura está publicada con saldo
- **THEN** el widget de anticipos lista la línea con su monto convertido a la moneda de la factura

#### Scenario: Pago VEF con revalorización

- **WHEN** un anticipo en VEF tiene `keep_alter_value_vef` activo
- **THEN** su monto en el widget se convierte desde el residual en VEF con la tasa de la fecha del pago

### Requirement: Cruce de anticipo al aplicarlo a una factura

Al aplicar un anticipo desde el widget (`js_assign_outstanding_line` sobre una línea cuyo asiento es de anticipo: `is_advance_move`, con `origin_payment_advanced_payment_id`, o cuyo pago origen tiene `is_advance_payment`), el sistema DEBE (MUST) crear un asiento de cruce ("CRUCE DE ANTICIPO") en el diario `advance_payment_igtf_journal_id` de la compañía activa, con una línea en la cuenta de anticipo y su contrapartida en la cuenta por cobrar/pagar de la factura por el mínimo entre el residual de la factura y el anticipo disponible según el widget, fechado en la fecha de conversión del widget (o en la fecha del pago cuando el pago tiene `keep_alter_value_vef`), publicarlo y conciliarlo doblemente: las líneas de anticipo contra el pago original y las líneas por cobrar/pagar contra la factura (`_reconcile_move_with_payment_difference`). DEBE (MUST) agregar la línea "IGTF" solo cuando el diario del pago es IGTF, el partner aplica IGTF según `_check_igtf_apply_improved`, el diario de la factura no es de compra internacional y el IGTF calculado con `calculate_igtf_for_payment` es mayor que cero; en ese caso, si el anticipo disponible alcanza, la base aplicada se incrementa con el IGTF convertido a la moneda del documento.

#### Scenario: Aplicación de anticipo simple

- **WHEN** se aplica un anticipo sin IGTF a una factura con saldo
- **THEN** se crea y publica un asiento de cruce por el monto aplicado y la factura queda conciliada por esa porción

#### Scenario: Anticipo con IGTF

- **WHEN** el pago de anticipo proviene de un diario IGTF, el partner aplica IGTF y el diario de la factura no es de compra internacional
- **THEN** el asiento de cruce incluye una línea "IGTF" contra la cuenta IGTF correspondiente y la contrapartida ajustada

#### Scenario: Anticipo aplicado a una importación

- **WHEN** la factura pertenece a un diario con `is_purchase_international`
- **THEN** el asiento de cruce se crea sin línea de IGTF

#### Scenario: Anticipo agotado

- **WHEN** el monto disponible del anticipo para la factura es cero
- **THEN** se lanza un error indicando que no se encontró el monto de anticipo a aplicar

### Requirement: Desaplicación de pagos y anticipos

`js_remove_outstanding_partial` DEBE (MUST): cuando la conciliación pertenece al asiento de un pago con cruces de anticipo activos (`advanced_move_ids` no cancelados) y ese asiento es el del propio pago, abrir el wizard `move.action.cancel.advance.payment.wizard` en lugar de desconciliar directamente; cuando el asiento es el de un cruce, ejecutar `remove_igtf_from_account_move` y luego desconciliar, cancelar y desvincular ese cruce (`cancel_advance_payment_transaction`); en el resto de casos ejecutar `remove_igtf_from_account_move` y, si este no actuó, delegar en el comportamiento nativo.

`remove_igtf_from_account_move` DEBE (MUST) pasar el asiento del pago a borrador, eliminar su línea IGTF trasladando el importe a la contrapartida por cobrar/pagar (reclasificada a la cuenta de anticipo del partner cuando la cuenta destino del pago no era de anticipo), marcar el pago como anticipo con `igtf_amount` 0, y finalmente volver a publicar el asiento —salvo que el asiento tenga `origin_payment_advanced_payment_id`, caso en el que se desvincula de `advanced_move_ids` y se cancela en lugar de publicarse—. Los pagos en la moneda VEF sin `origin_payment_advanced_payment_id` quedan fuera de este proceso y se desconcilian por el flujo nativo.

#### Scenario: Quitar un pago con cruces activos

- **WHEN** se desaplica desde la factura el pago origen de cruces de anticipo no cancelados
- **THEN** se abre el wizard de cancelación de anticipos en lugar de desconciliar

#### Scenario: Quitar un pago en divisa con IGTF

- **WHEN** se desaplica un pago en divisa cuyo asiento tiene línea IGTF
- **THEN** la línea IGTF se elimina, su importe se reintegra a la contrapartida sobre la cuenta de anticipo y el pago queda como anticipo disponible

#### Scenario: Quitar un pago en VEF sin cruces

- **WHEN** se desaplica un pago en VEF cuyo asiento no proviene de un cruce de anticipo
- **THEN** no se altera el asiento del pago y la conciliación se elimina por el flujo nativo

### Requirement: Wizard de cancelación de cruces de anticipo

`move.action.cancel.advance.payment.wizard.action_confirm` DEBE (MUST) desconciliar y cancelar cada asiento de cruce seleccionado, desvincularlo del pago (`advanced_move_ids` y `origin_payment_advanced_payment_id`), y luego quitar el IGTF del asiento del pago original desconciliándolo; `action_cancel` cierra el wizard sin cambios. Igualmente, `action_cancel` y `action_draft` de un pago con cruces activos DEBEN (MUST) abrir este wizard antes de proceder.

#### Scenario: Confirmación del wizard

- **WHEN** el usuario confirma la cancelación de los cruces
- **THEN** los asientos de cruce quedan cancelados, desvinculados del pago, y el pago queda sin línea IGTF y desconciliado

#### Scenario: Cancelar un pago con anticipos aplicados

- **WHEN** se cancela un pago que tiene asientos de cruce activos
- **THEN** se abre el wizard de cancelación en lugar de cancelar directamente

### Requirement: Asiento de remanente por pago en divisa con excedente

Tras crear pagos con IGTF desde el wizard (`_create_payments`), cuando el monto del pago supera lo adeudado más el IGTF y el manejo de la diferencia no es `reconcile`, el sistema DEBE (MUST) crear y publicar un asiento "RESTANTE DE PAGO EN DIVISA (nombre del pago)" en el diario de cruces (`advance_payment_igtf_journal_id` de la compañía activa) marcado con `is_advance_move` y `origin_payment_advanced_payment_id`, cuyo importe es el residual de la línea por cobrar/pagar del pago (no la diferencia calculada) y que traslada ese residual a la cuenta de anticipo del partner, y registrarlo en `advanced_move_ids`. El asiento no se crea cuando ese residual es cero, y la conciliación con el pago solo se ejecuta si tanto el asiento como el pago tienen líneas de tipo `asset_receivable` (cliente) o `liability_payable` (proveedor) marcadas además como cuenta de anticipo.

#### Scenario: Pago mayor a la deuda

- **WHEN** un pago con IGTF excede el total adeudado y la diferencia se mantiene abierta
- **THEN** se publica el asiento de remanente por el residual de la contrapartida del pago contra la cuenta de anticipo del partner y queda vinculado en `advanced_move_ids`

#### Scenario: Contrapartida del pago sin residual

- **WHEN** la línea por cobrar/pagar del pago no tiene residual
- **THEN** no se crea ningún asiento de remanente

### Requirement: Registro de pagos multi-factura homogéneo

`action_register_payment` de `account.move.line` DEBE (MUST) rechazar la selección cuando las líneas pertenecen a más de un partner, a más de una moneda o a más de una compañía.

#### Scenario: Facturas de dos clientes

- **WHEN** se registran pagos sobre facturas de partners distintos
- **THEN** se lanza un error pidiendo seleccionar facturas de un solo contacto

#### Scenario: Facturas en monedas distintas

- **WHEN** las facturas seleccionadas tienen monedas diferentes
- **THEN** se lanza un error indicando que deben tener la misma moneda

### Requirement: Pasar a borrador desconcilia el asiento

`button_draft` de `account.move` DEBE (MUST) eliminar las líneas analíticas y remover todas las conciliaciones de las líneas del asiento antes de devolverlo a borrador.

#### Scenario: Factura conciliada a borrador

- **WHEN** se pasa a borrador una factura con pagos conciliados
- **THEN** las conciliaciones se eliminan y el asiento queda en borrador

### Requirement: Columna IGTF en los libros fiscales

El módulo DEBE (MUST) extender los libros de ventas y compras de `l10n_ve_invoice` con un grupo/columna "IGTF" que muestra el `foreign_igtf_amount` de `tax_totals` de cada documento cuando su `alter_bi_igtf` es mayor que cero (0 en caso contrario), con signo negativo únicamente en las notas de crédito (`out_refund` en el libro de ventas, `in_refund` en el de compras); los flags `not_show_igtf_sale_order` / `not_show_igtf_purchase_order` de la compañía suprimen el grupo de columnas IGTF del Excel.

#### Scenario: Factura con IGTF en el libro de ventas

- **WHEN** una factura del libro tiene IGTF aplicado
- **THEN** su línea muestra el monto del IGTF en la columna IGTF

#### Scenario: Columna oculta

- **WHEN** la compañía activa `not_show_igtf_sale_order`
- **THEN** el libro de ventas se genera sin el grupo de columnas IGTF

### Requirement: Revalorización de pagos en VEF configurable

El campo `keep_alter_value_vef` de los pagos DEBE (MUST) inicializarse con `revalorize_payments_vef` de la compañía y desactivarse automáticamente cuando la moneda del pago no es la de la compañía (onchange `_onchange_keep_alter_value_vef`).

#### Scenario: Pago en divisa

- **WHEN** un pago se registra en una moneda distinta a la de la compañía
- **THEN** `keep_alter_value_vef` queda en falso

### Requirement: Clasificación de líneas del pago con cuentas de anticipo

`_seek_for_lines` de `account.payment` DEBE (MUST) clasificar como contrapartida del pago las líneas cuyas cuentas sean por cobrar, por pagar o corrientes (`asset_receivable`, `liability_payable`, `liability_current`, `asset_current`) —o cuyo partner sea el de la compañía—, permitiendo que los pagos anticipados con cuenta puente se sincronicen correctamente con su asiento. La contrapartida se devuelve por asignación y no por acumulación: cuando el asiento tiene varias líneas que cumplen la condición, solo la última recorrida se devuelve como contrapartida, y las líneas de liquidez y de write-off se siguen acumulando.

#### Scenario: Pago anticipado con cuenta puente

- **WHEN** el asiento de un pago anticipado tiene su contrapartida en una cuenta corriente de anticipo
- **THEN** esa línea se reconoce como contrapartida y no como write-off

#### Scenario: Asiento con varias líneas candidatas

- **WHEN** el asiento del pago tiene más de una línea sobre cuentas por cobrar/pagar o corrientes
- **THEN** la clasificación devuelve como contrapartida solo la última de esas líneas
