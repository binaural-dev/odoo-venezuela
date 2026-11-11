# l10n_ve_reconcile_assistant

## Purpose

Asistente de conciliación manual que aplica un pago o anticipo contra una o varias facturas con las mismas reglas que el widget de pagos de la factura de `l10n_ve_igtf` (fecha de conversión, tasa, IGTF y cruce de anticipo). La conciliación manual nativa no pasa por esas reglas. Añade el wizard `l10n_ve.reconcile.assistant` (con sus líneas `l10n_ve.reconcile.assistant.item`), el clasificador `_l10n_ve_reconcile_classify` y el campo `l10n_ve_open_amount` en `account.move.line`, y los ganchos `_l10n_ve_reconcile_is_special_note` y `_l10n_ve_reconcile_apply_context` en `account.move`. No depende de Enterprise (`l10n_ve_reconcile_assistant_accountant` conecta el botón Reconciliar). Depende de `l10n_ve_igtf`.

## Requirements

### Requirement: Clasificación de la selección

`account.move.line._l10n_ve_reconcile_classify` DEBE (MUST) clasificar cada línea como `invoice`, `payment`, `advance`, `cross` (asiento de cruce de anticipo), `note` (nota de IGTF o de diferencial cambiario) u `other`, y devolver `handled` (si el asistente se hace cargo de la selección), `ok` (si se puede conciliar), `case` (`payment` o `advance`), `origins`, `invoices` y `reasons`. Una selección sin factura y origen que no involucre anticipos, cruces ni notas NO DEBE (MUST NOT) ser tomada por el asistente (`handled` falso) y sigue por la conciliación nativa.

#### Scenario: Pago contra factura

- **WHEN** se selecciona una factura de cliente y un pago recibido
- **THEN** `handled` y `ok` son verdaderos y `case` es `payment`

#### Scenario: Selección que no es de este asistente

- **WHEN** se seleccionan dos pagos sin factura, o dos facturas sin pago
- **THEN** `handled` es falso

### Requirement: Anticipos disponibles, incluido el residual de un pago hecho de más

El clasificador DEBE (MUST) decidir por la línea y no por el asiento si algo es un anticipo disponible, porque `is_advance_move` marca tanto el asiento de cruce (que consume el anticipo) como el residual "RESTANTE DE PAGO EN DIVISA" que deja un pago hecho de más desde la factura (que lo deja disponible). Es un anticipo disponible la línea del lado del anticipo en su cuenta de anticipos (crédito en la de clientes, débito en la de proveedores) de un asiento con pago de origen, sea un anticipo registrado a mano o ese residual. El lado que consume sigue siendo un cruce y se bloquea. El pago de origen DEBE (MUST) leerse como en `_create_advance_payment_move`: `origin_payment_advanced_payment_id` y, si no, `origin_payment_id`; así la vista previa conoce el diario de IGTF del pago original.

#### Scenario: Cruzar el residual de un pago hecho de más

- **WHEN** se paga desde una factura de 100 USD un monto de 150 USD con diario de IGTF y luego se selecciona el residual de anticipo y otra factura de 40 USD
- **THEN** la selección es un anticipo contra una factura, la fila marca el diario con IGTF, el monto ofrecido coincide con el del widget de esa factura y al confirmar queda pagada

#### Scenario: Línea que consume el anticipo

- **WHEN** se selecciona la línea de la cuenta de anticipos que consume el anticipo en un asiento de cruce
- **THEN** la selección se bloquea como cruce de anticipo

### Requirement: Un solo origen contra una o varias facturas

El asistente DEBE (MUST) admitir un único pago o anticipo contra una o varias facturas, sin límite de facturas. Con más de un origen DEBE (MUST) bloquear explicando que cada pago se concilia por separado, porque cada pago convierte solo lo que le queda y cada anticipo crea sus propios asientos de cruce, de modo que el resultado dependería del orden.

#### Scenario: Un pago contra cinco facturas

- **WHEN** se selecciona un pago y cinco facturas del mismo socio
- **THEN** la selección es válida y la vista previa tiene cinco filas

#### Scenario: Dos pagos contra una factura

- **WHEN** se seleccionan dos pagos y una factura
- **THEN** la selección se bloquea con el motivo de origen único

### Requirement: Combinaciones bloqueadas

El asistente DEBE (MUST) bloquear, con el motivo en el wizard y sin botón Conciliar: líneas de un asiento de cruce de anticipo; líneas de notas de IGTF o de diferencial cambiario; un anticipo sin factura; un anticipo contra una cuenta que no es por cobrar ni por pagar; socios distintos; compañías distintas; líneas sin publicar o ya conciliadas; y un pago y facturas que van en el mismo sentido (por ejemplo un pago recibido contra una factura de proveedor). Un módulo adicional PUEDE (MAY) sumar motivos mediante `_l10n_ve_reconcile_extra_blockers`.

#### Scenario: Anticipo contra un asiento manual

- **WHEN** se selecciona un anticipo y una línea de gasto
- **THEN** el wizard abre bloqueado con el motivo y sin botón Conciliar

### Requirement: Vista previa sin escritura

El wizard DEBE (MUST) calcular, para cada par (origen, factura) y sin escribir ni consumir secuencias, el monto que ofrece el origen con lo que le queda tras los pares anteriores, convertido con la fecha y la tasa del widget de esa factura (la más reciente entre pago y factura, o la fecha del pago si mantiene el valor), limitado a lo que la factura aún debe. Cada fila DEBE (MUST) mostrar fecha de conversión, tasa (moneda de la compañía por unidad de la otra), monto a la factura, IGTF, saldo del origen antes, lo que se cruza y saldo del origen después, y lo pendiente de la factura. Para un anticipo DEBE (MUST) imitar `_create_advance_payment_move`, que consume `saldo × base ÷ monto del widget` con los montos redondeados, de modo que el saldo previsto sea el real. Un pago mayor que las facturas conserva saldo, igual que en el widget.

#### Scenario: Anticipo parcial contra dos facturas

- **WHEN** un anticipo de 300 USD con diario de IGTF se aplica a facturas de 100 y 80 USD
- **THEN** se cruzan 103,00 y 82,40 USD (con 3,00 y 2,40 de IGTF) y quedan 114,60 USD, que es el residual real del anticipo

#### Scenario: Anticipo en bolívares con tasas distintas por factura

- **WHEN** un anticipo de 8.000 Bs se aplica a facturas de 100 USD (tasa 40) y 80 USD (tasa 36)
- **THEN** la segunda fila convierte a la tasa 36, consume 2.880,03 Bs y deja 1.119,97 Bs, igual que el motor

### Requirement: Orden de aplicación editable

Las filas del wizard DEBEN (MUST) reordenarse arrastrándolas (campo `sequence` con widget `handle`), y al cambiar el orden `_onchange_item_ids` DEBE (MUST) recalcular la vista previa porque cada factura convierte solo lo que queda del origen con su propia regla de fecha y tasa. Las facturas arrancan ordenadas de la más antigua a la más reciente.

#### Scenario: Reordenar dos facturas

- **WHEN** el usuario arrastra la segunda factura a la primera posición
- **THEN** la vista previa se recalcula y al confirmar se respeta el nuevo orden

### Requirement: Aplicación par por par en una sola transacción

`action_confirm` DEBE (MUST) volver a clasificar la selección y, si ya no es válida, lanzar `UserError`; luego aplicar cada par en orden con `js_assign_outstanding_line` sobre la factura con `with_company(invoice.company_id)`, leyendo el widget de nuevo antes de cada par, saltando los pares cuyo origen ya quedó conciliado o cuya factura ya está pagada. Todo DEBE (MUST) correr en la transacción del botón: si un par falla, ninguno queda aplicado.

#### Scenario: Falla la segunda factura

- **WHEN** la aplicación de la segunda factura lanza un error
- **THEN** la primera factura sigue sin pagar y el origen sin conciliar

#### Scenario: Compañía activa distinta de la de la factura

- **WHEN** el usuario concilia con otra compañía activa
- **THEN** el cruce de anticipo se crea en la compañía de la factura, con su diario y su cuenta de IGTF

### Requirement: Permisos

Los modelos transitorios del asistente DEBEN (MUST) tener `ir.model.access.csv` para `account.group_account_user`, y el asistente NO DEBE (MUST NOT) usar `sudo()`. Un usuario sin ese grupo NO DEBE (MUST NOT) poder leer el wizard.

#### Scenario: Usuario sin acceso contable

- **WHEN** un usuario interno sin el grupo contable intenta leer `l10n_ve.reconcile.assistant`
- **THEN** se lanza `AccessError`

### Requirement: Ganchos para otros módulos

`_l10n_ve_reconcile_extra_blockers` (sobre `account.move.line`) DEBE (MUST) devolver una lista de motivos de bloqueo adicionales, y `_l10n_ve_reconcile_apply_context` (sobre `account.move`) un diccionario de contexto con el que se aplica el origen a esa factura, ambos vacíos por defecto.
