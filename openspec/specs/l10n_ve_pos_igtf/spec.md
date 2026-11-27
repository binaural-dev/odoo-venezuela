# l10n_ve_pos_igtf

## Purpose

Aplica el IGTF (Impuesto a las Grandes Transacciones Financieras) a los cobros del Punto de Venta: cálculo del recargo en el frontend según la moneda en que se cobra con cada método (la configuración por moneda de `l10n_ve_pos`, con «Aplicar IGTF»), cobro del recargo como parte del pago (nunca como impuesto de línea), validación backend de "orden pagada" contra el total con IGTF, un asiento propio que lleva el IGTF a la cuenta IGTF de la compañía y se concilia con el pago y la factura, y devolución en el reembolso del IGTF que se cobró en la venta. Extiende `pos.config`, `pos.order`, `pos.payment`, `pos.payment.method`, `pos.payment.method.currency` y `account.move`, y parchea los modelos y pantallas OWL del PdV. Depende de `l10n_ve_pos` (moneda alterna, conversión, configuración por moneda y contrato de sincronización) y de `l10n_ve_igtf` (campos `igtf_percentage` y `customer_account_igtf_id` en `res.company`, `bi_igtf` y los demás campos de IGTF en `account.move`).

En 20 el efectivo de una caja es un solo método que acepta varias monedas (ADR-023 de `l10n_ve_pos`), así que el IGTF se marca por método y moneda; en 19 se marcaba en el método, porque cada moneda tenía su método.

## Requirements

### Requirement: IGTF por método de pago y moneda, con el porcentaje de la compañía

Cada fila de la configuración por moneda de un método de pago (`pos.payment.method.currency`) DEBE (MUST) poder marcarse «Aplicar IGTF» (`apply_igtf`, columna de la lista de monedas del formulario del método, que viaja al PdV con la configuración), y `pos.config` exponer `igtf_percentage` como related editable de `company_id.igtf_percentage` (definido en `l10n_ve_igtf`), que es el porcentaje usado por el cálculo del frontend. Una línea de pago genera IGTF solo si la fila de su método para la moneda en que se cobra lo tiene marcado. En 19 se marcaba en el método.

#### Scenario: Configuración de la moneda del método

- **WHEN** un administrador marca «Aplicar IGTF» en la fila USD del método de efectivo
- **THEN** los pagos en dólares con ese método generan recargo IGTF usando el porcentaje de la compañía, y los pagos en euros o en bolívares con el mismo método no

#### Scenario: Pago en la moneda de la caja

- **WHEN** se cobra en bolívares con un método que solo tiene marcado el IGTF en USD
- **THEN** la línea no genera IGTF

### Requirement: El IGTF de los métodos de 19 pasa a su moneda

Al actualizar desde 19, después de que `l10n_ve_pos` une los métodos de pago de cada caja, el sistema DEBE (MUST) marcar «Aplicar IGTF» en la fila de cada moneda del método que queda si alguno de los métodos viejos que aportaron esa moneda tenía IGTF. Un método que cobraba en la moneda de la caja y tenía IGTF NO DEBE (MUST NOT) dejar IGTF en ninguna fila: no tiene dónde guardarlo, y queda listado en un aviso del registro de la actualización para que contabilidad decida. El paso NO DEBE (MUST NOT) aplicarse mientras la unión de `l10n_ve_pos` no se haya aplicado, ni borrar el plan de la unión, que lo borra `l10n_ve_pos` al final de la actualización. Una instalación nueva no hace nada.

#### Scenario: Efectivo en dólares con IGTF

- **WHEN** en 19 «Efectivo $» tenía IGTF y «Efectivo EUR» no, y los dos se unen en «Efectivo Bs.»
- **THEN** la fila USD de «Efectivo Bs.» queda con «Aplicar IGTF» y la de EUR sin él

#### Scenario: Zelle con IGTF

- **WHEN** en 19 Zelle, un banco en dólares, tenía IGTF
- **THEN** su fila USD queda con «Aplicar IGTF»

#### Scenario: Método en bolívares con IGTF

- **WHEN** en 19 un método que cobraba en bolívares tenía IGTF
- **THEN** ninguna fila queda con IGTF por él y el método aparece en el aviso del registro

#### Scenario: Unión todavía sin aplicar

- **WHEN** el plan de la unión de `l10n_ve_pos` tiene filas sin aplicar
- **THEN** no se marca nada y el plan se conserva

### Requirement: La caja no abre sin la cuenta IGTF cuando aplica IGTF

Antes de crear una sesión, el sistema DEBE (MUST) rechazarla con un error de validación cuando algún método de la caja tiene una moneda con «Aplicar IGTF» y la compañía no tiene `customer_account_igtf_id`. Una caja sin IGTF DEBE (MUST) abrir aunque falte la cuenta.

#### Scenario: Compañía sin cuenta IGTF

- **WHEN** se intenta abrir una sesión de una caja que aplica IGTF y `customer_account_igtf_id` está vacío
- **THEN** se lanza el error pidiendo configurar la cuenta y el porcentaje, y no se crea la sesión

#### Scenario: Caja sin IGTF

- **WHEN** ninguna moneda de los métodos de la caja tiene «Aplicar IGTF» y la compañía no tiene la cuenta
- **THEN** la sesión se abre

### Requirement: IGTF calculado sobre la base cubierta por cada pago

En una venta, `update_igtf()` (frontend, `order_model.js`) DEBE (MUST) recalcular el recargo recorriendo las líneas de pago en orden (`_igtfBaseState`, en espacio normalizado por el signo de `get_total_without_igtf()`): cada pago consume primero base de factura pendiente; solo la porción de base cubierta por una línea que aplica IGTF (por su método y su moneda) genera IGTF (`base * config.igtf_percentage / 100`, redondeo monetario local vía `roundLocalMoney`); el excedente de un pago salda deuda IGTF ya acumulada SIN generar más IGTF —incluida la que esa misma línea acaba de generar, porque el excedente se resta después de sumar `newIgtf`—; los pagos que no aplican IGTF consumen base sin generar recargo; las líneas de vuelto (monto negativo en el espacio normalizado) y las de monto cero no consumen base. Un reembolso que conoce el IGTF de su venta no sigue esta regla (ver «El reembolso devuelve el IGTF cobrado en la venta»).

El resultado se acumula en `igtf_amount`/`bi_igtf` de la orden (con signo, negativo en reembolsos) y en `include_igtf`/`igtf_amount`/`foreign_igtf_amount` de cada línea. `include_igtf` se pone en verdadero en TODA línea que aplica IGTF y no es vuelto, incluso cuando la base que cubrió es cero y por tanto su `igtf_amount` queda en cero.

#### Scenario: Pago completo con IGTF

- **WHEN** una línea que aplica IGTF cubre exactamente toda la base de la factura
- **THEN** la línea queda con `include_igtf` verdadero y su `igtf_amount` es el porcentaje sobre esa base, que pasa a ser nuevo restante de la orden

#### Scenario: Línea IGTF que no cubre base

- **WHEN** una línea que aplica IGTF llega cuando la base de la factura ya está cubierta y solo paga deuda IGTF
- **THEN** su `igtf_amount` queda en 0 pero `include_igtf` igualmente queda en verdadero

#### Scenario: Línea que salda deuda IGTF

- **WHEN** una segunda línea paga la deuda IGTF generada por la primera
- **THEN** la porción que salda deuda no genera IGTF adicional (no hay bucle del 3% sobre el 3%)

#### Scenario: Pago mixto

- **WHEN** parte de la base se paga en bolívares y el resto en una moneda con «Aplicar IGTF»
- **THEN** solo la porción de base cubierta por la línea que aplica IGTF genera recargo

### Requirement: Reseteo previo y guarda de orden a facturar

`update_igtf()` DEBE (MUST) empezar SIEMPRE poniendo en cero los cuatro montos de la orden (`igtf_amount`, `foreign_igtf_amount`, `bi_igtf`, `foreign_bi_igtf`) y llamando `set_include_igtf(false)`, `set_igtf_amount(0)` y `set_foreign_igtf_amount(0)` en TODAS las líneas de pago, antes de cualquier cálculo; y solo después, si la orden no tiene `to_invoice` activo, salir devolviendo `igtf_amount` en 0 sin recorrer las líneas.

Esa guarda es defensiva y no se alcanza en el stack instalado: `l10n_ve_pos` fuerza `to_invoice = true` en `PosOrder.setup()` y en `setToInvoice()` (SENIAT), y este módulo se apila por encima, de modo que toda orden del PdV llega a `update_igtf()` con `to_invoice` verdadero — incluido el `update_igtf()` que este módulo dispara desde su propio `setup()` y el que dispara `toggleIsToInvoice`.

#### Scenario: Recálculo normal

- **WHEN** se llama `update_igtf()` en una orden del PdV (siempre `to_invoice` verdadero por `l10n_ve_pos`)
- **THEN** los montos de la orden y los flags de todas las líneas se reinician y se vuelven a calcular

#### Scenario: Orden sin facturación (rama defensiva)

- **WHEN** `to_invoice` es falso porque otro módulo o un caso de datos lo desactivó
- **THEN** `igtf_amount`, `bi_igtf` y sus equivalentes foráneos quedan en 0 y ninguna línea lleva `include_igtf`

### Requirement: Lado foráneo del IGTF derivado con una sola conversión

En una venta, cada monto foráneo del IGTF (`foreign_igtf_amount`, `foreign_bi_igtf`) DEBE (MUST) derivarse convirtiendo UNA vez el monto local vía `localToForeign` de `l10n_ve_pos` (`_igtfToForeign`), nunca con un cálculo paralelo en divisa; y `get_foreign_total_paid_with_igtf()` sumar los dos valores foráneos ya derivados (total factura foráneo + IGTF foráneo) redondeando con la moneda alterna.

#### Scenario: Recibo con IGTF en divisa

- **WHEN** la orden generó IGTF
- **THEN** el total foráneo cobrado mostrado es exactamente la suma de las dos partes foráneas visibles (sin drift de redondeo)

### Requirement: El restante de la orden incluye la deuda IGTF

El getter `remainingDue` de la orden DEBE (MUST) devolver `(totalDue + igtf_amount) - amountPaid` cuando hay IGTF generado (con clamp a cero por signo y tolerancia de cash rounding vía `orderIsRounded`/`asymmetricRound`), delegando en el core (`PosOrderAccounting.remainingDue`) cuando `igtf_amount` es cero. Este getter es la precarga de toda línea de pago nueva: la línea toma la deuda de factura más la deuda IGTF acumulada, nunca el IGTF que su propia base generará (ese nace después, en `update_igtf()`).

Con esa precarga, cobrar una factura completa con una línea que aplica IGTF deja una segunda línea pendiente por el recargo. Pero NO hay nada que obligue a dos líneas: si el cajero teclea en una sola línea que aplica IGTF la base más el recargo, el excedente de esa misma línea absorbe en `_igtfBaseState` la deuda IGTF que ella acaba de generar (`unpaidIgtf` se reduce con el `excess` de la propia línea), el `igtf_amount` de la orden y de la línea se conserva, `amountPaid` cubre `totalDue + igtf_amount` y `remainingDue` queda en 0 con una única línea.

#### Scenario: Nueva línea tras generar IGTF

- **WHEN** una línea que aplica IGTF cubrió exactamente la base y se agrega una segunda línea
- **THEN** la segunda línea se precarga con la deuda IGTF pendiente (no con la deuda total del 3% de la factura)

#### Scenario: Cierre en una sola línea

- **WHEN** el cajero teclea en una sola línea que aplica IGTF la base más el 3%
- **THEN** el excedente de esa línea salda la deuda IGTF que generó y `remainingDue` devuelve 0 sin necesidad de una segunda línea

#### Scenario: Deuda IGTF parcialmente absorbida

- **WHEN** una línea absorbe parte de la deuda IGTF y su propia base genera nuevo recargo
- **THEN** `remainingDue` refleja solo la deuda pendiente real, no la deuda IGTF total acumulada

### Requirement: El vuelto respeta el total efectivo con IGTF

El getter `change` DEBE (MUST) calcular el vuelto contra el total efectivo `priceIncl + igtf_amount`, conservando la convención de signo del core (vuelto con signo opuesto al total: negativo en ventas), y devolver 0 mientras lo pagado no supere ese total efectivo.

#### Scenario: Sobrepago con IGTF

- **WHEN** lo pagado excede el total de la factura más el IGTF generado
- **THEN** el vuelto es el excedente sobre el total efectivo, con el signo que espera el backend para la línea `is_change`

### Requirement: Captura en divisa consciente del IGTF

Cuando el cajero teclea una línea en la moneda en que cobra (dólares o euros) con la orden a facturar y contexto IGTF (la línea aplica IGTF o la orden ya tiene deuda IGTF, con cualquier método), el sistema DEBE (MUST) tomar como adeudado la base de factura pendiente más la deuda IGTF, sin la propia línea, expresado en la moneda de la línea tal como se ve en pantalla, y si lo tecleado lo cubre:

- Si lo tecleado es ese adeudado más el IGTF que genera la propia línea, o la cifra «TOTAL a Pagar con IGTF» del panel (cuando la línea aplica IGTF, está en la moneda alterna y no hay nada pagado), la línea DEBE (MUST) valer exactamente ese total en bolívares, y la orden queda saldada sin restante ni vuelto. El panel suma por separado el total y el IGTF en divisa y puede quedar un céntimo arriba o abajo del total redondeado: las dos cifras saldan la orden.
- Si es el adeudado que se muestra, la línea DEBE (MUST) valer exactamente el adeudado en bolívares, y el IGTF que genera queda como nuevo restante.
- Si es más, la línea DEBE (MUST) valer lo entregado convertido a la tasa de su moneda, nunca menos que el adeudado.

En cualquier otro caso (pago parcial, sin contexto IGTF) delega en el comportamiento de `l10n_ve_pos`. En 19, teclear el total con IGTF que muestra el panel dejaba un restante de unos pocos bolívares (menos de medio céntimo de la divisa) que no dejaba validar.

#### Scenario: Pagar en una línea el «TOTAL a Pagar con IGTF»

- **WHEN** en una orden sin pagos el cajero teclea en dólares, en una línea que aplica IGTF, la cifra «TOTAL a Pagar con IGTF» del panel
- **THEN** la línea vale exactamente el total más el IGTF en bolívares y la orden queda sin restante ni vuelto

#### Scenario: Pagar la deuda IGTF en divisa

- **WHEN** el cajero teclea en divisa el monto que cubre la base pendiente más la deuda IGTF
- **THEN** el monto local de la línea queda exactamente en el restante local sin ruido de redondeo cambiario

#### Scenario: Sobrepago en divisa con IGTF

- **WHEN** el cajero teclea en una línea que aplica IGTF más que el adeudado más su IGTF
- **THEN** la línea vale lo entregado a la tasa de su moneda y el vuelto sale de ahí

### Requirement: Recalculo del IGTF en cada mutación de pagos

La pantalla de pago DEBE (MUST) recalcular el IGTF tras agregar una línea (desde la pantalla y desde el modelo de la orden), editar el monto seleccionado, alternar facturación y eliminar una línea, y al abrirse para un reembolso, una vez leído el IGTF de la venta original.

#### Scenario: Eliminar la línea que generó IGTF

- **WHEN** el cajero elimina la línea de pago que aplicaba IGTF
- **THEN** el recargo se recalcula y desaparece del restante y del panel de estado

### Requirement: El reembolso devuelve el IGTF cobrado en la venta

Al abrir la pantalla de pago de un reembolso, el PdV DEBE (MUST) leer de cada orden original lo que todavía puede devolver: el total de factura, el IGTF, su base y su alterno, es decir lo cobrado menos lo que devolvieron sus reembolsos anteriores que no estén en borrador ni cancelados. El reembolso DEBE (MUST) devolver de cada orden original la parte del IGTF que corresponde a lo que reembolsa, o todo el resto cuando reembolsa lo que queda, de modo que la suma de reembolsos parciales es exactamente el IGTF de la venta; un reembolso de varias órdenes reparte su total entre ellas según sus líneas.

Ese IGTF DEBE (MUST) entrar en el restante desde el principio, con cualquier método o moneda con que se pague, y las líneas del reembolso NO DEBEN (MUST NOT) generar IGTF propio. Se reparte en sus líneas para que la nota de crédito lo revierta: primero las que aplican IGTF, cada una hasta el porcentaje de su monto, y el resto en las demás, en su orden. El panel muestra el IGTF del reembolso aunque se pague en bolívares. Un reembolso de una venta sin IGTF no devuelve IGTF aunque se pague en divisa. Si no se pudo leer la orden original, el reembolso calcula el IGTF con sus líneas, como una venta.

En 19 el reembolso calculaba su IGTF con sus propias líneas de pago, como una venta: con la línea en bolívares primero la base del IGTF quedaba en el 97 % de la cobrada, un reembolso en bolívares de una venta en divisa no devolvía IGTF y uno en divisa de una venta sin IGTF lo generaba.

#### Scenario: Reembolso en bolívares de una venta pagada en divisa

- **WHEN** se reembolsa en «Efectivo Bs.» una venta de 11.043,20 Bs pagada con $12,29 que cobró 331,30 de IGTF
- **THEN** el restante del reembolso es 11.374,50, la línea en bolívares se precarga con ese monto, con menos no deja validar, y la nota de crédito revierte los 331,30 de IGTF

#### Scenario: Reembolso de una venta pagada en euros y bolívares

- **WHEN** se reembolsa una venta pagada con 5 € (IGTF 158,25) y bolívares, registrando primero la línea en bolívares y después los 5 €
- **THEN** el reembolso devuelve los 158,25 de IGTF, en cualquier orden en que se registren las líneas

#### Scenario: Reembolsos parciales

- **WHEN** una venta se reembolsa en dos partes
- **THEN** la primera devuelve el IGTF en proporción a lo que reembolsa y la segunda el resto exacto

#### Scenario: Reembolso en borrador

- **WHEN** existe un reembolso anterior en borrador o cancelado de la misma venta
- **THEN** no se descuenta de lo que la venta puede devolver

#### Scenario: Venta sin IGTF reembolsada en divisa

- **WHEN** se reembolsa en dólares, con un método que aplica IGTF, una venta que no cobró IGTF
- **THEN** el reembolso no lleva IGTF

### Requirement: Persistencia de los campos IGTF al sincronizar

La sincronización DEBE (MUST) enviar `igtf_amount` y `bi_igtf` de la orden en `PosOrder.serializeForORM`, e inyectar `include_igtf`, `igtf_amount` y `foreign_igtf_amount` en los comandos de `payment_ids` emparejando por `uuid` (las líneas hijas se serializan por recursión directa y no pasan por el serializador del pago). Estos campos NO se declaran en `_load_pos_data_fields` para no volverlos reactivos (evita el bucle de render/sync).

#### Scenario: Orden con IGTF validada

- **WHEN** la orden se sincroniza
- **THEN** `pos.order.igtf_amount`/`bi_igtf` y los campos IGTF de cada `pos.payment` quedan almacenados en el backend

### Requirement: Orden pagada solo cuando cubre el total con IGTF

El backend DEBE (MUST) validar el pago contra el total efectivo `amount_total + igtf_amount` (`_get_total_with_igtf`, redondeado con la moneda de la orden; `igtf_amount` es firmado, así que sirve igual para notas de crédito): `action_pos_order_paid` replica la comparación inline del core sustituyendo el total por el total con IGTF (con las mismas tolerancias de cash rounding) y termina escribiendo `state = "paid"`. `_is_pos_order_paid` — el que usa el asistente de pago desde backend — aplica el mismo total pero por la vía del core: lo pasa por `_get_rounded_amount` y CONSERVA la rama especial de reembolso, en la que si `refunded_order_id.amount_total + total_con_igtf` es cero el objetivo pasa a ser `-refunded_order_id.amount_paid` (el IGTF entra ahí solo indirectamente, por lo que se cobró en la orden original). Ambos métodos delegan íntegramente en el comportamiento nativo cuando `currency_id.is_zero(igtf_amount)`.

#### Scenario: Pago que no cubre el IGTF

- **WHEN** una orden con IGTF generado se intenta marcar pagada cubriendo solo `amount_total`
- **THEN** se lanza el error "Order ... is not fully paid"

#### Scenario: Pago que cubre el total con IGTF

- **WHEN** lo pagado es el total de la factura más el IGTF
- **THEN** la orden queda pagada

#### Scenario: Orden sin IGTF

- **WHEN** la orden no generó IGTF
- **THEN** la validación de pago es exactamente la nativa (vía `super()`)

### Requirement: El IGTF nunca entra en el total de la factura, solo en el monto pagado

El sistema DEBE (MUST) mantener el recargo IGTF fuera de `pos.order.amount_total` y de los totales de la factura: no se agrega ninguna línea de producto ni impuesto por él. El recargo viaja exclusivamente dentro de `pos.payment.amount` de las líneas que aplican IGTF —el frontend fija ese monto como base más IGTF— por lo que `pos.order.amount_paid` SÍ lo incluye; de ahí que la comparación de "orden pagada" tenga que usar `amount_total + igtf_amount` en vez de `amount_total`. Su contrapartida contable es el asiento de IGTF (ver «El IGTF se asienta aparte y se concilia con el pago y la factura»).

#### Scenario: Orden facturada con IGTF cobrado

- **WHEN** una orden de 100 se cobra con una línea que aplica IGTF y genera 3 de recargo
- **THEN** `amount_total` sigue siendo 100, la factura no lleva línea ni impuesto por los 3, `amount_paid` llega a 103 y los 3 aparecen en la cuenta IGTF del asiento de IGTF

### Requirement: La factura toma de la orden los campos de IGTF

La factura de una orden del PdV con IGTF DEBE (MUST) llevar como base imponible del IGTF (`bi_igtf`) la base de la orden (sin pasar del total de la factura), como IGTF cobrado (`alter_bi_igtf`) el IGTF de la orden, la base en la moneda de la factura (`foreign_bi_igtf`) y como tope (`igtf_top_aply`) el porcentaje de la compañía sobre la base; con varias órdenes, la suma de las de todas. Una nota de crédito NO DEBE (MUST NOT) llevar base ni IGTF en esos campos. `l10n_ve_igtf` los calcula de los asientos de pago de la factura, pero el PdV salda el IGTF en su propio asiento, así que se toman de la orden.

#### Scenario: Facturación de orden con IGTF

- **WHEN** se factura una orden con base IGTF de 116 e IGTF de 3,48, con la compañía al 3 %
- **THEN** la factura queda con base 116, IGTF cobrado 3,48 y tope 3,48

#### Scenario: Nota de crédito

- **WHEN** se factura un reembolso con IGTF
- **THEN** la nota de crédito queda con la base, el IGTF cobrado y el tope en cero

### Requirement: El IGTF se asienta aparte y se concilia con el pago y la factura

Cuando una orden con IGTF se factura, el sistema DEBE (MUST):

- dejar en la línea de plazo de la factura solo la base: el asiento del cobro del método (el del núcleo, ver `l10n_ve_pos`) lleva el monto entregado completo, base más IGTF;
- crear y publicar, por cada grupo de pagos (método y moneda) con IGTF, un asiento de dos líneas en el diario de cierre de la caja (`closing_journal_id`) que debita la cuenta por cobrar del cliente y acredita `customer_account_igtf_id` por el IGTF, con el IGTF en moneda alterna en las dos líneas, la tasa de la venta como tasa manual, la fecha de la orden en el día del usuario y una referencia con la orden, la factura y el método;
- conciliar ese asiento junto con el cobro y la factura, de modo que la cuenta por cobrar queda en cero y el IGTF en su cuenta.

En un reembolso el asiento va invertido y revierte el IGTF. Los cobros sin IGTF y los asientos del cierre de sesión quedan como los arma `l10n_ve_pos`. En 19 el cobro de la factura era un solo asiento de pago de tres líneas (cuenta por cobrar, IGTF y débito total); el monto de IGTF por cuenta es el mismo.

#### Scenario: Pago con IGTF

- **WHEN** se factura una orden de 116 cobrada por banco con 119,48 (IGTF 3,48)
- **THEN** la línea de plazo de la factura es de 116, el asiento de IGTF acredita 3,48 a la cuenta IGTF y debita 3,48 a la cuenta por cobrar, y la factura queda pagada con la cuenta por cobrar en cero y conciliada

#### Scenario: IGTF de dos métodos

- **WHEN** la orden se cobra con dos métodos que aplican IGTF
- **THEN** se crea un asiento de IGTF por método, y entre los dos suman el IGTF de la orden

#### Scenario: Pago sin IGTF

- **WHEN** ningún pago de la orden lleva IGTF
- **THEN** no se crea asiento de IGTF y la factura queda como la arma el núcleo

#### Scenario: Reembolso con IGTF

- **WHEN** se factura un reembolso que devuelve IGTF
- **THEN** el asiento de IGTF debita la cuenta IGTF y acredita la cuenta por cobrar, y la nota de crédito queda pagada

### Requirement: Panel de estado de pago con desglose IGTF

Cuando alguna línea de pago aplica IGTF, o el reembolso devuelve IGTF de su venta, el panel de estado de la pantalla de pago DEBE (MUST) mostrar la base imponible (`bi_igtf`), el IGTF generado, su equivalente foráneo y el renglón fijo "TOTAL a Pagar con IGTF" (en bolívares y en moneda alterna) calculado como total de factura más el porcentaje sobre la factura COMPLETA (`get_total_with_igtf`, valor de referencia que no varía con lo pagado); en un reembolso, su total más el IGTF que devuelve. Además, cada línea de pago con `include_igtf` muestra su recargo en formato "local / foráneo".

#### Scenario: Moneda con IGTF seleccionada

- **WHEN** el cajero agrega una línea en una moneda con «Aplicar IGTF»
- **THEN** aparece el bloque con BI IGTF, IGTF, Foreign IGTF y el total de referencia con IGTF

#### Scenario: Reembolso pagado en bolívares

- **WHEN** el cajero paga en bolívares un reembolso de una venta que cobró IGTF
- **THEN** el bloque aparece con el IGTF que devuelve el reembolso

### Requirement: Pantalla de pago exitoso con el IGTF realmente cobrado

La pantalla final del pago (la nativa de 20) DEBE (MUST) mostrar como monto cobrado el total de la factura más el IGTF realmente generado (`igtf_amount`), en la moneda del primer pago como hace el núcleo; debajo, cuando `l10n_ve_pos` muestra el total en moneda alterna (si el primer pago no es ya en esa moneda), ese total también con el IGTF (`get_foreign_total_paid_with_igtf`), y un renglón "IGTF: local / foráneo". Las órdenes sin IGTF muestran lo mismo que sin este módulo. En 19 la pantalla de recibo mostraba el total en bolívares y en moneda alterna en una sola línea.

#### Scenario: Cobro parcial con IGTF

- **WHEN** solo parte de la factura se pagó con una línea que aplica IGTF
- **THEN** la pantalla muestra factura + IGTF realmente generado (no el 3% de la factura completa)

#### Scenario: Orden sin IGTF

- **WHEN** la orden no generó IGTF
- **THEN** la pantalla muestra exactamente los totales que mostraba sin este módulo
