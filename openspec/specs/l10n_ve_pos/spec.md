# l10n_ve_pos

## Purpose

Adapta el Punto de Venta de Odoo 19 a la operación venezolana: tasa operativa de la caja tomada de `l10n_ve_rate`, manejo dual de montos (moneda principal y moneda alterna) en órdenes, pagos, asientos y reportes, facturación obligatoria de toda orden (SENIAT), reembolsos a la tasa histórica, movimientos de compensación (cross moves) para métodos de pago en divisa, carga de cadenas de listas de precios, formulario reducido de contacto para el cajero y permisos de caja. Extiende `pos.config`, `pos.session`, `pos.order`, `pos.order.line`, `pos.payment`, `pos.payment.method`, `account.move`, `account.partial.reconcile`, `account.tax`, `res.company`, `res.config.settings`, `res.currency`, `res.partner`, `res.users`, `stock.picking`, `product.product`, `product.category` y `product.pricelist`, e incluye un frontend OWL extenso bajo `static/src` empaquetado en `point_of_sale._assets_pos`. Depende de `point_of_sale`, `l10n_ve_rate`, `l10n_ve_contact`, `l10n_ve_stock`, `l10n_ve_location` y `l10n_ve_accountant`.

## Requirements

### Requirement: Tasa operativa de la caja calculada desde la tasa registrada

`pos.config` DEBE (MUST) exponer la moneda alterna de la compañía (`foreign_currency_id`, related a `company_id.foreign_currency_id`) y calcular `foreign_rate` y `foreign_inverse_rate` (campo con `digits=(16,15)`) mediante `res.currency.rate.compute_rate` de `l10n_ve_rate` con la fecha del día, quedando como tasa operativa de la sesión.

#### Scenario: Carga de la configuración de caja

- **WHEN** se computa `_compute_rate` de una caja cuya compañía tiene moneda alterna con tasa registrada
- **THEN** `foreign_rate` y `foreign_inverse_rate` toman los valores devueltos por `compute_rate` para esa moneda a la fecha actual

### Requirement: Apertura de sesión exige moneda alterna activa

El sistema DEBE (MUST) impedir abrir la interfaz del PdV (`pos.config._action_to_open_ui`) cuando la sesión no tiene `foreign_currency_id` o esa moneda no está activa, lanzando un error de validación.

#### Scenario: Compañía sin moneda alterna

- **WHEN** un cajero intenta abrir la caja y la compañía no tiene moneda alterna configurada o la moneda está archivada
- **THEN** se lanza un error indicando que la sesión debe tener una moneda alterna activa y la caja no se abre

### Requirement: Conversión centralizada con tasa completa y redondeo solo del resultado

La conversión entre moneda principal y alterna del PdV DEBE (MUST) hacerse multiplicando el monto por la tasa cruda sin redondear y redondeando únicamente el resultado con `to_currency.round()`. Para principal → alterna se usa `foreign_inverse_rate`; para alterna → principal se usa `foreign_rate`; misma moneda devuelve el monto (redondeado si se pide); sin tasa disponible devuelve `0.0`. Este contrato está implementado en espejo en `pos.config._convert` (backend) y en `PosOrder._convert` del frontend (`static/src/overrides/models/pos_order.js`).

#### Scenario: Conversión de bolívares a divisa

- **WHEN** se convierte un monto en moneda principal hacia la moneda alterna
- **THEN** el resultado es `monto * foreign_inverse_rate` redondeado con el redondeo de la moneda alterna

#### Scenario: Sin tasa configurada

- **WHEN** ninguna de las dos monedas involucradas es la moneda alterna, o la tasa operativa es cero
- **THEN** la conversión devuelve `0.0` (y el frontend registra una advertencia en consola una sola vez)

### Requirement: Facturación obligatoria de toda orden del PdV

Toda orden del PdV, incluidos los reembolsos, DEBE (MUST) emitir factura: el frontend fuerza `to_invoice = true` en `PosOrder.setup()` y en `setToInvoice()`, el botón nativo "Invoice" de la pantalla de pago se elimina de la plantilla (`payment_screen_button.xml`), y `shouldDownloadInvoice()` devuelve `false` para no descargar el PDF al validar.

#### Scenario: Venta normal

- **WHEN** el cajero crea una orden y la valida
- **THEN** la orden se sincroniza con `to_invoice` verdadero y genera factura, sin que exista botón para desactivarlo

#### Scenario: Reembolso

- **WHEN** se crea una orden de reembolso desde la pantalla de órdenes
- **THEN** el reembolso también lleva `to_invoice` verdadero (emite nota de crédito)

### Requirement: Cantidades negativas solo en líneas de reembolso

El sistema DEBE (MUST) impedir cantidades negativas en líneas que no sean de reembolso, en dos capas con las mismas exenciones: el frontend intercepta `setQuantity` y devuelve un diálogo de error, y el backend valida con el constraint `_check_qty_not_negative_outside_refund` sobre `pos.order.line.qty`. Están exentas las líneas con `refunded_orderline_id`, las líneas de órdenes con `is_refund` y las de órdenes con `preset_id.is_return`.

#### Scenario: Cantidad negativa desde el numpad

- **WHEN** el cajero intenta fijar una cantidad negativa en una línea de venta normal
- **THEN** se muestra un diálogo "Negative quantity not allowed" y la cantidad no cambia (poner la línea en cero sigue permitido)

#### Scenario: Línea negativa por RPC o edición backend

- **WHEN** se escribe una `qty` negativa en una línea sin `refunded_orderline_id` cuya orden no es reembolso ni tiene preset de devolución
- **THEN** se lanza un error de validación indicando que solo las líneas de reembolso pueden ser negativas

#### Scenario: Línea de reembolso real

- **WHEN** el flujo de reembolso crea una línea con `refunded_orderline_id` y cantidad negativa
- **THEN** la línea se acepta sin error

### Requirement: Totales alternos derivados del total local con una sola conversión

Los totales de la orden en moneda alterna (`get_foreign_total_with_tax`, `get_foreign_total_without_tax`, `get_foreign_total_tax`) DEBEN (MUST) obtenerse convirtiendo una sola vez el total local correspondiente (`totalDue`, `prices.taxDetails`) mediante `localToForeign`, y los montos por línea (`get_foreign_price_with_tax`, etc.) convertir cada precio local del core con la misma regla, de modo que la suma de líneas coincide con el total sin recalcular impuestos en divisa. El restante (`get_foreign_due`) y el vuelto (`get_foreign_change`) se derivan del restante/vuelto LOCAL con una conversión, no de la resta de totales alternos.

#### Scenario: Consistencia línea-total

- **WHEN** una orden sin líneas de reembolso tiene varias líneas con impuestos
- **THEN** la suma de `get_foreign_price_with_tax()` de las líneas coincide con `get_foreign_total_with_tax()` de la orden

#### Scenario: Pago parcial en moneda local

- **WHEN** el cliente paga parte de la orden con un método en moneda principal
- **THEN** `get_foreign_due()` disminuye, porque se deriva del `remainingDue` local (que descuenta todos los pagos) y no de la suma de `foreign_amount` de las líneas

### Requirement: Reembolsos convertidos a la tasa congelada de la venta original

Una línea de reembolso DEBE (MUST) convertir a moneda alterna usando `foreign_currency_rate` de la orden original (tasa congelada al sincronizarla), no la tasa viva de la caja (`_refundOriginalRate` en `pos_order_line.js`). Cuando la orden tiene líneas de reembolso, los totales alternos se calculan sumando los montos por línea ya convertidos a su tasa, y los montos derivados (restante, vuelto) aplican la razón efectiva total alterno / total local. En el backend, `_prepare_refund_data` propaga `foreign_price` de la línea original a la línea de reembolso.

#### Scenario: Reembolso con tasa distinta a la del día

- **WHEN** se reembolsa una orden vendida con una tasa anterior a la vigente
- **THEN** los montos alternos del reembolso se calculan con la tasa de la venta original y no con la tasa actual de la caja

### Requirement: Persistencia de los montos alternos al sincronizar

Al sincronizar una orden, el frontend DEBE (MUST) enviar `foreign_amount_total` (total alterno con impuestos) y `foreign_currency_rate` (multiplicador local → alterna vigente) en `PosOrder.serializeForORM`, y cada pago enviar `foreign_amount` y `foreign_rate` en `PosPayment.serializeForORM`. En el backend estos campos son `readonly` en `pos.order` y la lectura del loader (`_load_pos_data_read`) los reexpone al frontend.

#### Scenario: Orden sincronizada

- **WHEN** una orden validada llega al backend
- **THEN** `pos.order.foreign_amount_total` y `pos.order.foreign_currency_rate` quedan almacenados con los valores calculados por el frontend, y cada `pos.payment` conserva su `foreign_amount` y `foreign_rate`

### Requirement: Recalculo del monto alterno para todo método de pago

Cuando el monto local de una línea de pago cambia (`setAmount`), el sistema DEBE (MUST) recalcular `foreign_amount = localToForeign(amount)` para TODOS los métodos de pago, incluidos los métodos en moneda local (`_recomputeForeignFromLocal` en `payment_model.js`): el equivalente en divisa se necesita para la contabilidad dual aunque el cajero haya tecleado en bolívares.

#### Scenario: Pago en efectivo local

- **WHEN** el cajero registra un pago con un método sin `is_foreign_currency`
- **THEN** la línea de pago igualmente lleva `foreign_amount` con el equivalente en moneda alterna

### Requirement: Captura de monto en divisa con liquidación exacta del adeudado

Cuando el cajero teclea el monto en divisa (`set_foreign_amount`), el sistema DEBE (MUST): si el monto en divisa cubre el adeudado en divisa (comparación con la precisión de la moneda alterna vía `comp`/`isZero`), fijar el `amount` local EXACTAMENTE al restante local (más el sobrepago convertido, si existe), absorbiendo el ruido de redondeo cambiario; si es un pago parcial, aplicar la conversión matemática estricta `foreignToLocal`. El adeudado en divisa se deriva del restante LOCAL antes de esta línea, convertido una sola vez.

#### Scenario: Pago que cubre el total

- **WHEN** el monto en divisa tecleado es igual o mayor (dentro de la tolerancia de redondeo) al adeudado en divisa
- **THEN** el `amount` local de la línea queda en el restante local exacto y la orden queda saldada sin residuo de céntimos

#### Scenario: Pago parcial en divisa

- **WHEN** el monto en divisa tecleado es menor al adeudado
- **THEN** el `amount` local es la conversión estricta del monto tecleado

### Requirement: Línea de pago en divisa precargada y editada en divisa

En la pantalla de pago, al agregar una línea con un método `is_foreign_currency`, el sistema DEBE (MUST) precargar la línea con el adeudado local convertido a divisa (`set_foreign_amount`) y poblar el buffer numérico con formato de locale (nunca `toFixed`, que rompe el parseo en `es_VE`); las ediciones posteriores del monto de esa línea pasan por `set_foreign_amount`, y si la caja no tiene método de efectivo, un monto que exceda en valor absoluto el adeudado se rechaza reponiendo el máximo permitido.

#### Scenario: Agregar método en divisa

- **WHEN** el cajero pulsa un método de pago marcado `is_foreign_currency` con adeudado pendiente
- **THEN** la línea nace con el adeudado expresado en divisa y el buffer muestra ese valor con el separador decimal del locale

#### Scenario: Monto mayor al adeudado sin efectivo configurado

- **WHEN** el cajero teclea en una línea en divisa un monto mayor al límite y ningún método de la caja es de efectivo
- **THEN** se muestra el error de valor máximo y el monto se repone al adeudado

### Requirement: Validación de orden sin líneas de pago en cero

Al validar la orden, el sistema DEBE (MUST) rechazar la validación con un diálogo "Empty Paymentline" si alguna línea de pago tiene monto `0` o el total de la orden es `0` (`_isOrderValid` en `payment_screen.js`).

#### Scenario: Línea vacía

- **WHEN** el cajero pulsa validar con una línea de pago en cero
- **THEN** aparece el diálogo de error y la orden no se valida

### Requirement: Consulta de pagos de la orden original en reembolsos

En un reembolso, la pantalla de pago DEBE (MUST) ofrecer el botón "View Payments Origin", que consulta por RPC `pos.order.get_payments_order_refund` con las órdenes origen de las líneas reembolsadas y muestra en un popup los pagos originales con método y monto alterno.

#### Scenario: Reembolso con orden origen

- **WHEN** el cajero abre la pantalla de pago de un reembolso y pulsa el botón
- **THEN** se listan los pagos de la orden original (método, etiqueta y monto en divisa o local)

### Requirement: Botón de reembolso total en la pantalla de órdenes

La pantalla de tickets DEBE (MUST) incluir el botón "Reembolso total", que fija como cantidad a reembolsar de cada línea la cantidad aún reembolsable (`qty - refundedQty`), omitiendo las líneas ya vinculadas a una orden de reembolso destino y las que no tienen cantidad reembolsable.

#### Scenario: Orden parcialmente reembolsada

- **WHEN** el cajero pulsa "Reembolso total" sobre una orden con una línea ya parcialmente reembolsada
- **THEN** esa línea queda marcada con la cantidad restante por reembolsar y las demás con su cantidad completa

### Requirement: La factura del PdV hereda la tasa de la orden

La factura generada por una orden del PdV DEBE (MUST) crearse con `foreign_rate` y `foreign_inverse_rate` iguales a `foreign_currency_rate` de la orden y `manually_set_rate = True` (`_prepare_invoice_vals`), y cada línea de factura recibir el `foreign_price` de su línea de orden (`_get_invoice_lines_values`), de modo que `l10n_ve_accountant` no recalcule la tasa con la del día.

#### Scenario: Facturación de la orden

- **WHEN** el backend factura una orden del PdV
- **THEN** la factura lleva la tasa congelada de la orden y sus líneas el precio alterno de la venta

### Requirement: Asientos de pago de factura con montos alternos y tasa del pago

`pos.payment._create_payment_moves` DEBE (MUST) escribir en el asiento de pago generado `foreign_rate`/`foreign_inverse_rate` iguales al `foreign_rate` del pago con `manually_set_rate = True`, y en cada apunte fijar `foreign_debit`/`foreign_credit` con el valor absoluto de `foreign_amount` del pago (según el lado con saldo) marcando `not_foreign_recalculate = True`.

#### Scenario: Pago de orden facturada

- **WHEN** el cierre genera el asiento de pago de una factura del PdV
- **THEN** los apuntes llevan los montos alternos del pago y la tasa pactada, sin que el compute base de `l10n_ve_accountant` los sobreescriba

### Requirement: Cierre de sesión con montos alternos en la contabilidad

Durante el cierre de sesión, el sistema DEBE (MUST) acumular `foreign_amount` de cada pago de las órdenes cerradas en los mismos buckets que el core (`_accumulate_amounts`/`_update_amounts`, por pago si `split_transactions` y por método si no, para efectivo, banco y facturas), y escribir `foreign_debit`/`foreign_credit` con `not_foreign_recalculate = True` en las líneas receivable de los asientos de banco, de efectivo (incluida la contrapartida no-receivable del mismo asiento) y de facturas. El asiento de cierre de la sesión y los `account.payment` combinados/split reciben `foreign_rate`/`foreign_inverse_rate` de la configuración de la caja.

#### Scenario: Método bancario combinado

- **WHEN** se cierra una sesión con pagos de un método banco sin `split_transactions`
- **THEN** la línea receivable del asiento combinado lleva como `foreign_debit`/`foreign_credit` la suma de los `foreign_amount` de esos pagos

#### Scenario: Orden en borrador con pago

- **WHEN** existe una orden en estado `draft`/`cancel` con un pago registrado
- **THEN** el acumulador no le crea bucket (solo itera `_get_closed_orders()`) y no se genera un asiento en cero

### Requirement: Cross moves de compensación para métodos en divisa

Al cerrar la sesión (`action_pos_session_close` → `_validate_cross_move`), por cada método de pago con `is_foreign_currency`, tipo distinto de `pay_later` y ambos diarios configurados (`cross_account_journal` y `cross_journal`), el sistema DEBE (MUST) crear en `cross_account_journal` asientos EN BORRADOR que trasladan el saldo de la cuenta transitoria del método (cuenta por defecto del diario para efectivo; cuenta outstanding para banco) hacia la cuenta real del `cross_journal`, con `foreign_debit`/`foreign_credit`, tasa del pago y una referencia (`ref`) que identifica sesión/orden/pago; el número secuencial (`name`) se deja vacío para que lo asigne el diario al contabilizar. Un método sin alguno de los dos diarios se omite en silencio.

#### Scenario: Método en divisa completo

- **WHEN** se cierra una sesión con pagos de un método `is_foreign_currency` con ambos diarios configurados
- **THEN** se crean asientos borrador en `cross_account_journal` que acreditan la cuenta transitoria y debitan la cuenta real del `cross_journal` (o a la inversa para montos negativos)

#### Scenario: Configuración incompleta

- **WHEN** al método le falta `cross_account_journal` o `cross_journal`
- **THEN** no se crea ningún cross move para ese método y el cierre no falla

### Requirement: Granularidad del cross move según split_transactions

La granularidad de los cross moves DEBE (MUST) seguir el flag nativo `split_transactions` del método: con `split_transactions` verdadero se crea un asiento por cada `pos.payment` (referenciando orden y pago); con falso, un único asiento por método y sesión con el neto de todos sus pagos, sin crear nada si el neto es cero. Si el partner de un pago pertenece a otra compañía, se omite del encabezado del asiento (las líneas lo conservan).

#### Scenario: Método identificando cliente

- **WHEN** el método tiene `split_transactions` activo y la sesión registró tres pagos con él
- **THEN** se crean tres asientos borrador, cada uno con la referencia de su pago

#### Scenario: Neto cero combinado

- **WHEN** el método no divide transacciones y las ventas y devoluciones del método se anulan entre sí
- **THEN** no se crea ningún asiento para ese método

### Requirement: Bloqueo de pasar a borrador asientos de una sesión abierta

`account.move.button_draft` DEBE (MUST) rechazar con error el paso a borrador de un asiento vinculado a una sesión de PdV aún abierta, salvo que la compañía tenga activo `pos_move_to_draft` (configurable en Binaural Settings).

#### Scenario: Sesión abierta sin permiso

- **WHEN** un usuario intenta pasar a borrador un asiento relacionado a una sesión en estado `opened` y `pos_move_to_draft` está desactivado
- **THEN** se lanza un error y el asiento no cambia de estado

### Requirement: Bloqueo de romper conciliaciones de una sesión abierta

El sistema DEBE (MUST) impedir eliminar una conciliación parcial (`account.partial.reconcile`) cuando alguno de sus apuntes pertenece a una factura de una sesión de PdV abierta, salvo que la compañía tenga activo `pos_unreconcile_moves`.

#### Scenario: Romper conciliación con sesión abierta

- **WHEN** se intenta desconciliar un pago de una factura de una sesión abierta con `pos_unreconcile_moves` desactivado
- **THEN** se lanza un error de validación y la conciliación se mantiene

### Requirement: Carga de cadenas de listas de precios encadenadas

La carga de listas de precios al PdV (`product.pricelist._load_pos_data_domain`) DEBE (MUST) incluir el cierre transitivo de las listas base: partiendo de las listas disponibles del core, se agregan recursivamente todas las listas alcanzables por items con `base='pricelist'` a cualquier profundidad, con protección contra ciclos. Además, si una lista base de la cadena usa montos absolutos (`price_surcharge`, `price_round`, `price_min_margin`, `price_max_margin`), se registra una advertencia en el log porque su moneda puede no estar cargada en la caja.

#### Scenario: Cadena de tres niveles

- **WHEN** la lista operativa en Bs se ancla a una intermedia que a su vez se ancla a una lista en divisa con los precios fijos
- **THEN** las tres listas viajan al frontend y `getPrice()` resuelve el precio de la cadena en vez de caer a `list_price`

### Requirement: Carga on-demand de items de listas base

`pos.session.get_pos_ui_product_pricelist_item_by_product` DEBE (MUST) complementar la respuesta del core con los items (y los registros de lista) de las listas base de la cadena que no están entre las disponibles de la caja, aplicando el mismo dominio de vigencia y compañía del core y deduplicando por id, para que los productos cargados por búsqueda lleguen con sus precios fijos.

#### Scenario: Producto encontrado por búsqueda

- **WHEN** el cajero busca un producto no precargado y su precio fijo vive en una lista base en divisa
- **THEN** la respuesta incluye los items de esa lista base y el registro de la lista, y el precio mostrado coincide con el del servidor

### Requirement: Monedas cargadas al PdV restringidas y ordenadas

El loader de `res.currency` DEBE (MUST) restringir las monedas enviadas al PdV a la moneda de la compañía, la moneda de la caja y la moneda alterna (`_load_pos_data_domain`), exponer `inverse_rate` entre los campos y devolver la lista con la moneda de la compañía en primera posición (`_load_pos_data_read`).

#### Scenario: Compañía con moneda alterna

- **WHEN** se abre una caja de una compañía con moneda alterna configurada
- **THEN** al frontend llegan únicamente esas monedas, con la de la compañía primero

### Requirement: Permisos para cambiar cantidad y precio en la caja

El módulo DEBE (MUST) restringir los botones de cantidad y precio del numpad a los usuarios con los grupos `l10n_ve_pos.group_change_qty_on_pos_order` y `l10n_ve_pos.group_change_price_on_pos_order` respectivamente: el loader de `res.users` expone los flags como `_can_change_qty_on_pos_order` / `_can_change_price_on_pos_order` (calculados con `has_group` en servidor) y `ProductScreen.getNumpadButtons` deshabilita el botón correspondiente cuando el flag es falso. Ambos grupos se definen sin `privilege_id` para comportarse como permisos independientes.

#### Scenario: Cajero sin permiso de precio

- **WHEN** un usuario sin el grupo de cambio de precio abre la pantalla de productos
- **THEN** el botón "price" del numpad aparece deshabilitado

#### Scenario: Cajero con ambos grupos

- **WHEN** el usuario pertenece a ambos grupos
- **THEN** los botones de cantidad y precio funcionan normalmente

### Requirement: Visibilidad y orden de productos según disponibilidad

Con el flag de compañía `pos_show_just_products_with_available_qty` activo, el sistema DEBE (MUST) ordenar el catálogo cargado al PdV por `qty_available` descendente (`_sort_available_products`) y el frontend excluir de `productsToDisplay` los productos cuyo tipo no es `service` ni `consu` y cuya `qty_available` no es positiva. El loader de productos expone `free_qty` y `qty_available` calculados con el almacén del tipo de operación de la caja.

#### Scenario: Flag activo

- **WHEN** la compañía activa el flag y se abre la caja
- **THEN** los productos llegan ordenados por disponibilidad descendente, computada contra el almacén de la caja

### Requirement: Existencia disponible en la tarjeta de producto

Con `pos_show_free_qty` activo en la compañía, la tarjeta de producto DEBE (MUST) mostrar la cantidad disponible obtenida en vivo vía `getProductInfo` (con debounce), leyendo `available_quantity` del primer almacén reportado.

#### Scenario: Consulta de stock de la tarjeta

- **WHEN** se renderiza la tarjeta de un producto con el flag activo
- **THEN** se consulta la información del producto y se muestra la cantidad disponible (0 si la consulta falla)

### Requirement: Endpoints de validación de stock del PdV

El controlador DEBE (MUST) exponer las rutas JSON `/validate_products_order` y `/validate_products_in_warehouse`: la primera devuelve `msg_error` con el nombre del producto si un producto almacenable tipo `consu` no tiene `qty_available` suficiente; la segunda valida las cantidades contra los quants del almacén de la caja y devuelve `msg_error` si no alcanza el stock en ese almacén o si el producto no existe en él — salvo que se pase `sell_kit_from_another_store` verdadero, que permite vender productos sin stock en el almacén de la caja.

#### Scenario: Stock insuficiente en el almacén de la caja

- **WHEN** se llama `/validate_products_in_warehouse` con una cantidad mayor a la disponible en el almacén del picking type
- **THEN** la respuesta incluye un `msg_error` indicando el producto y el almacén

### Requirement: Formulario reducido de contacto exclusivo del PdV

El PdV DEBE (MUST) abrir la creación/edición de clientes con la vista `l10n_ve_pos.view_partner_form_pos`, derivada de `base.view_partner_form` en `mode="primary"` (hereda los campos de `l10n_ve_contact` y `l10n_ve_location` ya combinados) que elimina botones inteligentes, foto, sitio web, idioma, etiquetas, propiedades y el notebook completo, y sustituye el campo `function` por `barcode`. La acción `point_of_sale.res_partner_action_edit_pos` se sobreescribe para apuntar a esa vista con el contexto `l10n_ve_pos_partner_defaults`, sin modificar el formulario de Contactos del backoffice.

#### Scenario: Crear cliente desde la caja

- **WHEN** el cajero abre el diálogo de cliente del PdV
- **THEN** ve el formulario reducido con el bloque de identificación (`prefix_vat` + `vat`) y la dirección venezolana

#### Scenario: Mismo contacto en el backoffice

- **WHEN** un usuario abre ese contacto desde Contactos
- **THEN** ve el formulario completo de `base.view_partner_form`, intacto

### Requirement: Precarga de la dirección de la compañía en contactos nuevos del PdV

Con el flag de contexto `l10n_ve_pos_partner_defaults`, el `default_get` de `res.partner` DEBE (MUST) precargar `country_id`, `state_id`, `city_id`, `municipality`, `parish_id` y `zip` desde `env.company.partner_id`, respetando cualquier valor ya resuelto por `super()` (claves `default_*` del contexto o defaults de campo), omitiendo los campos vacíos en la compañía, y sin precargar nada cuando el contacto es hijo (`parent_id` o `default_parent_id` presentes) o cuando el contexto no trae el flag.

#### Scenario: Contacto nuevo desde la caja

- **WHEN** el cajero crea un cliente y la compañía tiene la dirección completa
- **THEN** los seis campos aparecen precargados con los valores del partner de la compañía

#### Scenario: Creación desde el backoffice

- **WHEN** se crea un partner sin el flag de contexto
- **THEN** el `default_get` nativo no se altera

#### Scenario: Contacto hijo

- **WHEN** el formulario se abre con `default_parent_id` en el contexto
- **THEN** ningún campo se precarga desde la compañía (hereda del padre por el mecanismo nativo)

### Requirement: El campo city (Char) nunca se escribe por el mecanismo de defaults

El mecanismo de precarga DEBE (MUST) excluir el campo `city` (Char, `related="city_id.name"` almacenado y escribible) de los defaults de compañía: escribirlo directamente renombraría el registro `res.country.city` referenciado. Solo se precarga `city_id`; el Char se completa vía el related.

#### Scenario: Precarga sin efecto colateral

- **WHEN** el `default_get` precarga `city_id` con la ciudad de la compañía
- **THEN** la clave `city` no está entre los defaults y ningún registro `res.country.city` se modifica

### Requirement: Indicador de alícuota y precio alterno por línea de orden

Cada línea del carrito DEBE (MUST) mostrar junto al nombre del producto el indicador fiscal `(G)` (gravado) o `(E)` (exento) — `(E)` cuando la línea no tiene impuestos o el primer impuesto tiene `amount == 0` (`get_aliquot_type`) — y junto al precio local su equivalente en moneda alterna (`get_foreign_price_with_tax`).

#### Scenario: Producto exento

- **WHEN** se agrega al carrito un producto sin impuestos o con impuesto de tasa 0
- **THEN** la línea muestra `(E)` y su precio alterno

### Requirement: Visualización de la tasa de cambio operativa

El PdV DEBE (MUST) mostrar la tasa operativa normalizada a la semántica "1 divisa = X local" (si la tasa cruda es menor a 1 se muestra su inverso), formateada con la precisión decimal `Tasa` (`get_display_rate`/`getConversionRateForDisplay`). Si no hay tasa disponible se muestra "N/D" y se alerta una única vez por orden con un diálogo pidiendo configurar la tasa.

#### Scenario: Tasa cruda invertida

- **WHEN** la configuración expone la tasa como factor menor a 1
- **THEN** en pantalla se muestra `1/tasa` con la precisión de `Tasa`

#### Scenario: Tasa faltante

- **WHEN** no existe tasa operativa
- **THEN** se muestra "N/D" y aparece la alerta "Tasa de conversión faltante" una sola vez

### Requirement: Recibo y pantallas con totales en moneda alterna

El recibo y las pantallas del PdV DEBEN (MUST) exponer los totales alternos: `export_for_printing` agrega `foreign_amount_total`, `foreign_total_without_tax`, `foreign_amount_tax` y `foreign_total_paid` al payload de impresión; la pantalla de recibo muestra el total alterno junto al local; la pantalla de pago muestra el total alterno adeudado y el panel de estado muestra Foreign Total / Foreign Remaining / Foreign Change (con clamp a cero de residuos negativos por redondeo); la pantalla de tickets muestra total, impuesto alterno y tasa de la orden seleccionada. El formateo usa `env.utils.formatForeignCurrency`, registrado por el override del servicio `contextual_utils_service` con la moneda alterna de la caja.

#### Scenario: Impresión del recibo

- **WHEN** se imprime el recibo de una orden
- **THEN** el payload contiene los cuatro totales alternos calculados por los getters de la orden

#### Scenario: Residuo negativo por redondeo

- **WHEN** el restante alterno calculado es un residuo negativo por debajo del redondeo de la moneda
- **THEN** el panel de estado muestra 0 y no un valor negativo

### Requirement: Reporte de detalles de venta con totales en divisa

`get_sale_details` DEBE (MUST) extender el reporte nativo con la moneda alterna de la compañía: agrega `f_total` (suma de `foreign_amount` por método y sesión, vía SQL) a cada pago, el agregado `payments_per_method` con total local y alterno por método, y `foreign_total_paid` como total general en divisa; la plantilla QWeb añade las columnas correspondientes solo si hay moneda alterna.

#### Scenario: Compañía sin moneda alterna

- **WHEN** la compañía no tiene `foreign_currency_id`
- **THEN** el reporte devuelve la estructura nativa con `foreign_total_paid = 0.0` y sin desglose en divisa

#### Scenario: Sesión con pagos en varios métodos

- **WHEN** se genera el detalle de ventas de una sesión con pagos
- **THEN** cada método muestra su total en divisa y el total general en divisa es la suma redondeada con la moneda alterna

### Requirement: Reporte de métodos de pago del PdV

El wizard `pos.payment.report` DEBE (MUST) generar el reporte `l10n_ve_pos.payment_report_pos` filtrado por rango de fechas (convertido a la zona horaria del usuario), cajas, categorías de producto y nivel de categorías (1er nivel, 2do nivel o ambos), mostrando por método de pago y por categoría los montos en moneda principal y en moneda alterna con su porcentaje sobre el total.

#### Scenario: Generación del reporte

- **WHEN** el usuario selecciona rango, cajas y categorías y pulsa generar
- **THEN** se emite el reporte con los pagos agrupados por método (conteo, monto local y alterno formateados) y el desglose por categorías seleccionadas

### Requirement: Grupo de descuento autorizado en el PdV

El módulo DEBE (MUST) definir el grupo `l10n_ve_pos.group_authorized_discount_pos` ("Authorized discount pos") bajo el privilegio del Punto de Venta, disponible para que las personalizaciones restrinjan la aplicación de descuentos.

#### Scenario: Asignación del grupo

- **WHEN** un administrador edita un usuario
- **THEN** el grupo "Authorized discount pos" está disponible dentro del privilegio del Punto de Venta
