# l10n_ve_pos_igtf

## Purpose

Aplica el IGTF (Impuesto a las Grandes Transacciones Financieras) a los cobros del Punto de Venta: cálculo del recargo en el frontend según los métodos de pago marcados `apply_igtf`, cobro del recargo como parte del pago (nunca como impuesto de línea), validación backend de "orden pagada" contra el total con IGTF, y asientos de pago con la línea separada hacia la cuenta IGTF de la compañía. Extiende `pos.config`, `pos.order`, `pos.payment`, `pos.payment.method` y `pos.session`, y parchea los modelos y pantallas OWL del PdV. Depende de `l10n_ve_pos` (moneda alterna, conversión y contrato de sincronización) y de `l10n_ve_igtf` (campos `igtf_percentage` y `customer_account_igtf_id` en `res.company`, `bi_igtf` en `account.move`).

## Requirements

### Requirement: Método de pago con IGTF y porcentaje por compañía

Cada método de pago (`pos.payment.method`) DEBE (MUST) poder marcarse con `apply_igtf` (visible en su formulario y cargado al frontend vía `_load_pos_data_fields`), y `pos.config` exponer `igtf_percentage` como related editable de `company_id.igtf_percentage` (definido en `l10n_ve_igtf`), que es el porcentaje usado por el cálculo del frontend.

#### Scenario: Configuración del método

- **WHEN** un administrador marca `apply_igtf` en un método de pago de la caja
- **THEN** los pagos del PdV con ese método generan recargo IGTF usando el porcentaje de la compañía

### Requirement: Apertura de sesión exige la cuenta IGTF configurada

`pos.session.action_pos_session_open` DEBE (MUST) lanzar un error de validación cuando la compañía no tiene `customer_account_igtf_id` configurada, impidiendo abrir la sesión.

#### Scenario: Compañía sin cuenta IGTF

- **WHEN** se intenta abrir una sesión y `customer_account_igtf_id` está vacío
- **THEN** se lanza el error pidiendo configurar la cuenta y el porcentaje, y la sesión no se abre

### Requirement: IGTF calculado sobre la base cubierta por cada pago

`update_igtf()` (frontend, `order_model.js`) DEBE (MUST) recalcular el recargo recorriendo las líneas de pago en orden (`_igtfBaseState`): cada pago consume primero base de factura pendiente; solo la porción de base cubierta por una línea con `apply_igtf` genera IGTF (`base * igtf_percentage / 100`, redondeo monetario local); el excedente de cualquier pago salda deuda IGTF ya generada SIN generar más IGTF; los pagos sin `apply_igtf` consumen base sin generar recargo. El resultado se acumula en `igtf_amount` y `bi_igtf` de la orden (con signo, negativo en reembolsos) y en `include_igtf`/`igtf_amount` de cada línea.

#### Scenario: Pago completo con método IGTF

- **WHEN** una línea con `apply_igtf` cubre toda la base de la factura
- **THEN** la línea queda con `include_igtf` verdadero y su `igtf_amount` es el porcentaje sobre esa base, que pasa a ser nuevo restante de la orden

#### Scenario: Línea que salda deuda IGTF

- **WHEN** una segunda línea paga la deuda IGTF generada por la primera
- **THEN** la porción que salda deuda no genera IGTF adicional (no hay bucle del 3% sobre el 3%)

#### Scenario: Pago mixto

- **WHEN** parte de la base se paga con un método sin `apply_igtf` y el resto con uno con `apply_igtf`
- **THEN** solo la porción de base cubierta por el método con `apply_igtf` genera recargo

### Requirement: IGTF solo en órdenes a facturar

`update_igtf()` DEBE (MUST) dejar todos los montos IGTF en cero cuando la orden no tiene `to_invoice` activo, reseteando también los flags de las líneas de pago.

#### Scenario: Orden no facturada

- **WHEN** una orden no está marcada a facturar
- **THEN** `igtf_amount`, `bi_igtf` y sus equivalentes foráneos quedan en 0 y ninguna línea lleva `include_igtf`

### Requirement: Lado foráneo del IGTF derivado con una sola conversión

Los montos foráneos del IGTF (`foreign_igtf_amount`, `foreign_bi_igtf`) DEBEN (MUST) derivarse convirtiendo UNA vez el monto local vía `localToForeign` de `l10n_ve_pos` (`_igtfToForeign`), nunca con un cálculo paralelo en divisa; y `get_foreign_total_paid_with_igtf()` sumar los dos valores foráneos ya derivados (total factura foráneo + IGTF foráneo) redondeando con la moneda alterna.

#### Scenario: Recibo con IGTF en divisa

- **WHEN** la orden generó IGTF
- **THEN** el total foráneo cobrado mostrado es exactamente la suma de las dos partes foráneas visibles (sin drift de redondeo)

### Requirement: El restante de la orden incluye la deuda IGTF

El getter `remainingDue` de la orden DEBE (MUST) devolver `(totalDue + igtf_amount) - amountPaid` cuando hay IGTF generado (con clamp a cero por signo y tolerancia de cash rounding), delegando en el core cuando `igtf_amount` es cero. Este getter es la precarga de toda línea de pago nueva: la línea toma la deuda de factura más la deuda IGTF acumulada, nunca el IGTF que su propia base generará (ese nace después en `update_igtf()`; pagar una factura completa con un método `apply_igtf` produce siempre dos líneas).

#### Scenario: Nueva línea tras generar IGTF

- **WHEN** una línea con `apply_igtf` cubrió la base y se agrega una segunda línea
- **THEN** la segunda línea se precarga con la deuda IGTF pendiente (no con la deuda total del 3% de la factura)

#### Scenario: Deuda IGTF parcialmente absorbida

- **WHEN** una línea absorbe parte de la deuda IGTF y su propia base genera nuevo recargo
- **THEN** `remainingDue` refleja solo la deuda pendiente real, no la deuda IGTF total acumulada

### Requirement: El vuelto respeta el total efectivo con IGTF

El getter `change` DEBE (MUST) calcular el vuelto contra el total efectivo `priceIncl + igtf_amount`, conservando la convención de signo del core (vuelto con signo opuesto al total: negativo en ventas), y devolver 0 mientras lo pagado no supere ese total efectivo.

#### Scenario: Sobrepago con IGTF

- **WHEN** lo pagado excede el total de la factura más el IGTF generado
- **THEN** el vuelto es el excedente sobre el total efectivo, con el signo que espera el backend para la línea `is_change`

### Requirement: Captura en divisa consciente del IGTF

`set_foreign_amount` de la línea de pago DEBE (MUST), cuando la orden está a facturar y hay contexto IGTF (método `apply_igtf` o deuda IGTF acumulada), calcular el adeudado como base de factura pendiente más deuda IGTF (excluyendo la propia línea, vía `_igtfBaseState`), y si el monto en divisa tecleado lo cubre, fijar el monto local EXACTO (`dueLocal` más el sobrepago convertido) sin ida y vuelta de conversión; en cualquier otro caso delega en el comportamiento de `l10n_ve_pos`.

#### Scenario: Pagar deuda IGTF en divisa

- **WHEN** el cajero teclea en divisa el monto que cubre la base pendiente más la deuda IGTF
- **THEN** el monto local de la línea queda exactamente en el restante local sin ruido de redondeo cambiario

### Requirement: Recalculo del IGTF en cada mutación de pagos

La pantalla de pago DEBE (MUST) invocar `update_igtf()` y re-renderizar tras agregar una línea (`addNewPaymentLine` y `addPaymentline` del modelo), editar el monto seleccionado (`updateSelectedPaymentline`), alternar facturación (`toggleIsToInvoice`) y eliminar una línea (`deletePaymentLine`).

#### Scenario: Eliminar la línea que generó IGTF

- **WHEN** el cajero elimina la línea de pago con `apply_igtf`
- **THEN** el recargo se recalcula y desaparece del restante y del panel de estado

### Requirement: Persistencia de los campos IGTF al sincronizar

La sincronización DEBE (MUST) enviar `igtf_amount` y `bi_igtf` de la orden en `PosOrder.serializeForORM`, e inyectar `include_igtf`, `igtf_amount` y `foreign_igtf_amount` en los comandos de `payment_ids` emparejando por `uuid` (las líneas hijas se serializan por recursión directa y no pasan por el serializador del pago). Estos campos NO se declaran en `_load_pos_data_fields` para no volverlos reactivos (evita el bucle de render/sync).

#### Scenario: Orden con IGTF validada

- **WHEN** la orden se sincroniza
- **THEN** `pos.order.igtf_amount`/`bi_igtf` y los campos IGTF de cada `pos.payment` quedan almacenados en el backend

### Requirement: Orden pagada solo cuando cubre el total con IGTF

El backend DEBE (MUST) validar el pago contra el total efectivo `amount_total + igtf_amount` (`_get_total_with_igtf`, redondeado con la moneda de la orden): `action_pos_order_paid` replica la comparación del core sustituyendo el total por el total con IGTF (con las mismas tolerancias de cash rounding) y `_is_pos_order_paid` aplica el mismo criterio; las órdenes con `igtf_amount` cero delegan íntegramente en el comportamiento nativo.

#### Scenario: Pago que no cubre el IGTF

- **WHEN** una orden con IGTF generado se intenta marcar pagada cubriendo solo `amount_total`
- **THEN** se lanza el error "Order ... is not fully paid"

#### Scenario: Orden sin IGTF

- **WHEN** la orden no generó IGTF
- **THEN** la validación de pago es exactamente la nativa (vía `super()`)

### Requirement: La factura recibe la base imponible del IGTF

`_create_invoice` DEBE (MUST) escribir en la factura generada `bi_igtf` con el valor absoluto del `bi_igtf` de la orden, alimentando el campo homónimo de `account.move` definido en `l10n_ve_igtf`.

#### Scenario: Facturación de orden con IGTF

- **WHEN** el backend factura una orden cuyo `bi_igtf` es distinto de cero
- **THEN** la factura queda con esa base imponible IGTF registrada

### Requirement: Asientos de pago con línea separada hacia la cuenta IGTF

`pos.payment._create_payment_moves` DEBE (MUST) reimplementar la creación del asiento de pago para las líneas con `include_igtf`: acredita el monto del IGTF en `customer_account_igtf_id` de la compañía (con `foreign_debit`/`foreign_credit` del `foreign_igtf_amount` y `not_foreign_recalculate`), acredita la porción base restante en la cuenta por cobrar del cliente (con el foráneo sin IGTF), y debita el total en la cuenta receivable del PdV; los pagos sin `include_igtf` generan el par crédito/débito estándar con sus montos foráneos. El asiento se contabiliza y luego recibe `foreign_rate`/`foreign_inverse_rate` del pago con `manually_set_rate = True` para que `l10n_ve_accountant` no lo recalcule a la tasa del día.

#### Scenario: Pago con IGTF

- **WHEN** el cierre genera el asiento de un pago con `include_igtf`
- **THEN** el asiento tiene una línea de crédito hacia la cuenta IGTF por el recargo, otra hacia la cuenta por cobrar por la base, y el débito total, todos con sus montos foráneos y la tasa del pago

#### Scenario: Pago sin IGTF

- **WHEN** el pago no incluye IGTF
- **THEN** el asiento tiene el par crédito/débito estándar con `foreign_debit`/`foreign_credit` del `foreign_amount` del pago

### Requirement: Panel de estado de pago con desglose IGTF

Cuando alguna línea de pago usa un método `apply_igtf`, el panel de estado de la pantalla de pago DEBE (MUST) mostrar la base imponible (`bi_igtf`), el IGTF generado, su equivalente foráneo y el renglón fijo "TOTAL a Pagar con IGTF" calculado como total de factura más el porcentaje sobre la factura COMPLETA (`get_total_with_igtf`, valor de referencia que no varía con lo pagado). Además, cada línea de pago con `include_igtf` muestra su recargo en formato "local / foráneo".

#### Scenario: Método IGTF seleccionado

- **WHEN** el cajero agrega una línea con un método `apply_igtf`
- **THEN** aparece el bloque con BI IGTF, IGTF, Foreign IGTF y el total de referencia con IGTF

### Requirement: Pantalla de pago exitoso con el IGTF realmente cobrado

La pantalla de recibo DEBE (MUST) mostrar el total efectivamente cobrado usando el IGTF real de la orden (`igtf_amount`, vía `orderAmountPlusTip` reescrito y `get_foreign_total_paid_with_igtf` para el foráneo), con un renglón de desglose "IGTF: local / foráneo"; las órdenes sin IGTF delegan en el comportamiento nativo y en el total foráneo puro de `l10n_ve_pos`.

#### Scenario: Cobro parcial con IGTF

- **WHEN** solo parte de la factura se pagó con un método `apply_igtf`
- **THEN** la pantalla muestra factura + IGTF realmente generado (no el 3% de la factura completa)

#### Scenario: Orden sin IGTF

- **WHEN** la orden no generó IGTF
- **THEN** la pantalla muestra exactamente los totales que mostraba sin este módulo
