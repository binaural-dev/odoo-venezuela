# l10n_ve_pos

## Purpose

Adapta el Punto de Venta de Odoo 20 a la operación venezolana: tasa operativa de la caja tomada de `l10n_ve_rate`, manejo dual de montos (moneda principal y moneda alterna) en órdenes, pagos, asientos y reportes, facturación obligatoria de toda orden (SENIAT), reembolsos a la tasa histórica, movimientos de compensación (cross moves) de los cobros en divisa, carga de cadenas de listas de precios, formulario reducido de contacto para el cajero y permisos de caja.

En 20 el cobro en divisa usa la multimoneda nativa del PdV (ADR-023): un solo método de efectivo por caja acepta bolívares, dólares y euros, el cajero elige la moneda al pagar y el pago guarda la moneda en que se cobró. Lo que en 19 colgaba de cada método en divisa (`is_foreign_currency`, diarios de cruce) cuelga ahora de la configuración de cada moneda del método (`pos.payment.method.currency`, modelo nuevo de este módulo). La actualización desde 19 une los métodos de efectivo de cada caja en uno.

Extiende `pos.config`, `pos.session`, `pos.order`, `pos.order.line`, `pos.order.receipt`, `pos.payment`, `pos.payment.method`, `pos.make.payment`, `account.move`, `account.bank.statement.line`, `account.partial.reconcile`, `account.tax`, `res.company`, `res.config.settings`, `res.currency`, `res.partner`, `res.users`, `stock.picking`, `product.product`, `product.category`, `product.pricelist` y `pos.load.mixin`, agrega `pos.payment.method.currency`, e incluye un frontend OWL extenso bajo `static/src` empaquetado en `point_of_sale._assets_pos`. Depende de `point_of_sale`, `l10n_ve_rate`, `l10n_ve_contact`, `l10n_ve_stock`, `l10n_ve_location` y `l10n_ve_accountant`. El IGTF de los cobros en divisa lo agrega `l10n_ve_pos_igtf`, sobre la configuración por moneda de este módulo. El Kiosko y el autopedido móvil los ajusta `l10n_ve_pos_self_order`, con su propia spec en `l10n_ve_pos_self_order/openspec/specs` ("Mostrar solamente los productos disponibles" en `pos-self-order-kiosk-available-products`).

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

#### Scenario: Caja sin tasa del día

- **WHEN** `pos.config._compute_rate` se calcula un día sin tasa cargada para la moneda alterna
- **THEN** llama a `compute_rate` con `raise_if_not_found=False` y no lanza error (la configuración de la caja sigue accesible, aunque `l10n_ve_rate.compute_rate` lance `UserError` por defecto)

### Requirement: Facturación obligatoria de toda orden del PdV

Toda orden del PdV, incluidos los reembolsos, DEBE (MUST) emitir factura: el frontend fuerza `to_invoice = true` en `PosOrder.setup()` y en `setToInvoice()`, el botón nativo "Invoice" de la pantalla de pago se elimina de la plantilla (`payment_screen_button.xml`), y `shouldDownloadInvoice()` devuelve `false` para no descargar el PDF al validar.

#### Scenario: Venta normal

- **WHEN** el cajero crea una orden y la valida
- **THEN** la orden se sincroniza con `to_invoice` verdadero y genera factura, sin que exista botón para desactivarlo

#### Scenario: Reembolso

- **WHEN** se crea una orden de reembolso desde la pantalla de órdenes
- **THEN** el reembolso también lleva `to_invoice` verdadero (emite nota de crédito)

### Requirement: Cantidades negativas solo en líneas de reembolso

El sistema DEBE (MUST) impedir cantidades negativas en líneas que no sean de reembolso, en dos capas con exenciones DISTINTAS:

- Frontend (`pos_order_line.js`, `setQuantity` → `_isRefundLine()`): exime solo las líneas con `refunded_orderline_id` y las de órdenes con `preset_id.is_return`. Una línea añadida a mano a una orden con `is_refund` NO está exenta en esta capa.
- Backend (constraint `_check_qty_not_negative_outside_refund` sobre `pos.order.line.qty`, con `@api.constrains("qty", "refunded_orderline_id", "order_id")`): exime `refunded_orderline_id`, `order_id.is_refund` y `order_id.preset_id.is_return`.

La comparación usa la precisión `Product Unit`, así que la cantidad cero sigue permitida en ambas capas.

#### Scenario: Cantidad negativa desde el numpad

- **WHEN** el cajero intenta fijar una cantidad negativa en una línea de venta normal
- **THEN** `setQuantity` devuelve `{title: "Negative quantity not allowed", body: ...}`, `OrderSummary` lo muestra como diálogo y la cantidad no cambia (poner la línea en cero sigue permitido)

#### Scenario: Línea nueva negativa dentro de una orden de reembolso

- **WHEN** el cajero agrega al carrito de una orden con `is_refund` una línea sin `refunded_orderline_id` (y sin preset de devolución) y la pone en negativo desde el numpad
- **THEN** el frontend la rechaza con el mismo diálogo, aunque el constraint del backend sí la habría aceptado

#### Scenario: Línea negativa por RPC o edición backend

- **WHEN** se escribe una `qty` negativa en una línea sin `refunded_orderline_id` cuya orden no tiene `is_refund` ni preset de devolución
- **THEN** se lanza un error de validación indicando que solo las líneas de reembolso pueden ser negativas

#### Scenario: Línea de reembolso real

- **WHEN** el flujo de reembolso crea una línea con `refunded_orderline_id` y cantidad negativa
- **THEN** la línea se acepta sin error en ambas capas

### Requirement: Totales alternos derivados del total local con una sola conversión

Cada total de la orden en moneda alterna (`get_foreign_total_with_tax`, `get_foreign_total_without_tax`, `get_foreign_total_tax`) DEBE (MUST) obtenerse convirtiendo una sola vez el total local correspondiente (`totalDue`, `prices.taxDetails.base_amount`, `prices.taxDetails.tax_amount_currency`) mediante `localToForeign`, y los montos por línea (`get_foreign_price_with_tax`, etc.) convertir cada precio local del core (`priceIncl`, `priceExcl`) con la misma regla, sin recalcular nunca impuestos en divisa. El restante (`get_foreign_due`) y el vuelto (`get_foreign_change`) se derivan del restante/vuelto LOCAL con una conversión, no de la resta de totales alternos.

#### Scenario: Consistencia línea-total

- **WHEN** una orden sin líneas de reembolso tiene varias líneas con impuestos
- **THEN** cada línea devuelve `localToForeign(priceIncl)` y la orden devuelve `localToForeign(totalDue)` — ambos con la misma tasa cruda y una sola multiplicación — sin recalcular impuestos en divisa; la suma de las líneas puede diferir del total de la orden en múltiplos del paso de redondeo de la moneda alterna, porque cada línea se redondea por separado y el total se redondea una sola vez sobre el agregado

#### Scenario: Pago parcial en moneda local

- **WHEN** el cliente paga parte de la orden con un método en moneda principal
- **THEN** `get_foreign_due()` disminuye, porque se deriva del `remainingDue` local (que descuenta todos los pagos) y no de la suma de `foreign_amount` de las líneas

### Requirement: Reembolsos convertidos a la tasa congelada de la venta original

Una línea de reembolso DEBE (MUST) convertir a moneda alterna usando `foreign_currency_rate` de la orden original (tasa congelada al sincronizarla), no la tasa viva de la caja (`_refundOriginalRate` en `pos_order_line.js`). Cuando la orden tiene líneas de reembolso, los totales alternos se calculan sumando los montos por línea ya convertidos a su tasa, y los montos derivados (restante, vuelto) aplican la razón efectiva total alterno / total local. En el backend, `_prepare_refund_data` propaga `foreign_price` de la línea original a la línea de reembolso.

Un pago del reembolso en la moneda alterna de la compañía DEBE (MUST) valorarse con la tasa exacta con que se registraron los pagos de la venta original en esa moneda (`get_refund_foreign_rate`). Esa tasa congelada solo existe para la moneda alterna: un pago del reembolso en otra moneda (euros) se valora con la tasa de esa moneda que tiene cargada la caja.

#### Scenario: Reembolso con tasa distinta a la del día

- **WHEN** se reembolsa una orden vendida con una tasa anterior a la vigente
- **THEN** los montos alternos del reembolso se calculan con la tasa de la venta original y no con la tasa actual de la caja

#### Scenario: Reembolso en dólares de una venta cobrada en dólares

- **WHEN** el cajero devuelve en dólares los $45 que el cliente pagó en la venta original
- **THEN** la línea del reembolso vale en bolívares lo mismo que registró el pago original de $45

#### Scenario: Reembolso en euros

- **WHEN** el cajero registra una línea del reembolso en euros
- **THEN** su monto en bolívares sale de la tasa del euro que tiene cargada la caja, no de la tasa de la venta original

### Requirement: Persistencia de los montos alternos al sincronizar

Al sincronizar una orden, el sistema DEBE (MUST) guardar en ella el total en moneda alterna con impuestos (`foreign_amount_total`) y el multiplicador moneda principal → alterna con que se vendió (`foreign_currency_rate`), y en cada pago su monto en moneda alterna (`foreign_amount`), su tasa (`foreign_rate`) y, si se cobró en una moneda distinta de la de la orden, esa moneda (`foreign_currency_id`) y lo que el cliente entregó en ella (`amount_currency`). Los dos campos de la orden son de solo lectura y viajan de vuelta al PdV cuando este carga órdenes.

El servidor DEBE (MUST) completar lo que el PdV no manda: un pago sin tasa (de un PdV con un paquete anterior o de una orden encolada sin conexión) recibe la de la orden, o la de la venta original si es un reembolso; el vuelto, que lo crea el servidor, recibe su alterno calculado con la tasa de la orden; y el alterno de la orden y de cada pago, y el monto en la moneda del pago, toman el signo del monto local, de modo que un reembolso nunca queda con montos alternos positivos.

#### Scenario: Orden sincronizada

- **WHEN** una orden validada llega al backend
- **THEN** la orden guarda su total alterno y su tasa, y cada pago su alterno, su tasa y, si se cobró en divisa, la moneda y el monto entregado

#### Scenario: Pago sin tasa

- **WHEN** llega una orden cuyo pago no trae `foreign_rate`
- **THEN** el pago queda con la tasa de la orden (o la de la venta original, si es un reembolso)

#### Scenario: Reembolso con montos alternos positivos

- **WHEN** un PdV con un paquete anterior envía un reembolso con monto local negativo y alterno positivo
- **THEN** antes de marcar la orden pagada el alterno de la orden, el de cada pago y el monto en la moneda del pago quedan negativos, con la misma magnitud

### Requirement: Un solo método de efectivo por caja que cobra en varias monedas

Un método de pago de tipo efectivo o banco DEBE (MUST) poder aceptar varias monedas (las de su campo nativo «Monedas», `currency_ids`) y el cajero DEBE (MUST) elegir en la pantalla de pago la moneda en que cobra con él; el pago guarda esa moneda y lo entregado en ella. Una misma orden DEBE (MUST) poder cobrarse en varias monedas a la vez (por ejemplo bolívares, dólares y euros): el PdV de 20 lo prohíbe y este módulo lo vuelve a permitir, como en 19. Un método cuyas monedas no incluyen la de la caja (Zelle, solo en dólares) NO DEBE (MUST NOT) ofrecer bolívares: con una sola moneda, su botón cobra directamente en ella.

Un pago en una moneda distinta de la alterna de la compañía (euros) DEBE (MUST) valorarse con la tasa de esa moneda. En 19 había un método de efectivo por moneda («Efectivo Bs.», «Efectivo $», «Efectivo EUR») y el efectivo en euros se valoraba como si fueran dólares; en 20 hay un botón «Efectivo» y la elección de la moneda.

#### Scenario: Cobro en dólares con el efectivo único

- **WHEN** el cajero pulsa «Efectivo», elige USD y cobra $12
- **THEN** la línea de pago queda en dólares, con su equivalente en bolívares, y el pago se guarda con la moneda USD y $12 entregados

#### Scenario: Orden pagada en tres monedas

- **WHEN** el cajero agrega a la misma orden una línea en bolívares, otra en dólares y otra en euros
- **THEN** las tres líneas se aceptan y la orden se valida cuando suman el total

#### Scenario: Método sin la moneda de la caja

- **WHEN** el cajero pulsa Zelle, configurado solo con USD, en una caja en bolívares
- **THEN** no se le ofrece cobrar en bolívares y la línea nace en dólares

#### Scenario: Pago en euros

- **WHEN** el cajero cobra 10,56 € de una orden de 11.043,20 Bs
- **THEN** el monto en bolívares de la línea sale de la tasa del euro, no de la del dólar

### Requirement: Configuración de cada moneda del método de pago

El formulario del método de pago DEBE (MUST) mostrar, para un método de efectivo o banco con monedas, la lista «Configuración por moneda» (`pos.payment.method.currency`): una fila por moneda con el diario del asiento de cruce (`cross_account_journal`, de tipo misceláneo) y el diario que recibe los cobros de esa moneda (`cross_journal`, de banco o efectivo), ambos de la compañía del método. La lista NO DEBE (MUST NOT) editarse mientras el método tenga sesiones abiertas.

El sistema DEBE (MUST) rechazar una segunda fila para la misma moneda del mismo método y una fila con una moneda que no esté entre las monedas del método; y al quitar una moneda del método DEBE (MUST) borrar su fila. La configuración viaja al PdV con los métodos de pago. Los módulos que deciden algo por moneda la extienden: `l10n_ve_pos_igtf` le agrega «Aplicar IGTF».

#### Scenario: Diarios de cruce del efectivo en dólares

- **WHEN** el administrador agrega USD a las monedas del efectivo y en su fila elige el diario de cruce y el diario «Efectivo $»
- **THEN** los cobros en dólares de ese método usan esos diarios y los cobros en euros no

#### Scenario: Moneda repetida

- **WHEN** se intenta crear una segunda fila de USD en el mismo método
- **THEN** el sistema lo rechaza

#### Scenario: Moneda que no es del método

- **WHEN** se intenta crear una fila de EUR en un método cuyas monedas son solo USD
- **THEN** se lanza un error de validación que nombra la moneda y el método

#### Scenario: Quitar una moneda

- **WHEN** el administrador quita EUR de las monedas de un método que tenía filas de USD y de EUR
- **THEN** la fila de EUR desaparece y la de USD se conserva

### Requirement: Permisos sobre la configuración por moneda

La configuración por moneda de los métodos de pago DEBE (MUST) poder leerla todo usuario del PdV y solo el administrador del PdV DEBE (MUST) poder crearla, modificarla o borrarla. Un usuario NO DEBE (MUST NOT) ver la configuración de métodos de una compañía a la que no tiene acceso.

#### Scenario: Cajero

- **WHEN** un usuario con solo el grupo de usuario del PdV abre la caja o lee la configuración de un método
- **THEN** la ve, pero si intenta crear, modificar o borrar una fila recibe un error de acceso

#### Scenario: Administrador del PdV

- **WHEN** un usuario con el grupo de administrador del PdV edita la configuración de monedas de un método de su compañía
- **THEN** puede crear, modificar y borrar filas

#### Scenario: Usuario de otra compañía

- **WHEN** un usuario que solo tiene acceso a otra compañía busca la configuración por moneda o lee una fila de esta compañía
- **THEN** la búsqueda no la devuelve y la lectura da error de acceso

### Requirement: Fusión de los métodos de pago de una caja que viene de 19

Al actualizar desde 19, el sistema DEBE (MUST) dejar en cada caja un solo método de efectivo que acepte las monedas de los demás y conservar sus diarios de cruce y sus pagos:

- Sobrevive el método de efectivo que cobraba en la moneda de la caja (la de su diario o, si no tiene, la de la compañía). Un método en divisa cobraba en la moneda de su diario de cruce (o en la alterna de la compañía, si ese diario no tiene moneda); uno que no lo era, en la de su diario (o en la de la compañía). En una caja en bolívares sobrevive el efectivo en Bs.; en una caja en dólares, el efectivo en dólares. Si ningún efectivo cobraba en la moneda de la caja, sobrevive el primero que no era en divisa (por secuencia) o, si todos lo eran, el primero.
- Cada otro método de efectivo de la caja suma su moneda a las monedas del que sobrevive, sus diarios de cruce pasan a la fila de esa moneda en la configuración por moneda, sus pagos se mueven al que sobrevive con su moneda, y queda archivado y fuera de las cajas. Un segundo efectivo en la moneda de la caja se une sin moneda: sus pagos se mueven tal cual y queda archivado.
- Un método de banco que cobraba en otra moneda (Zelle, o un pago móvil en bolívares en una caja en dólares) conserva su identidad: solo gana su moneda, la fila con sus diarios de cruce y la moneda en sus pagos. Los de banco en la moneda de la caja no cambian.
- El monto entregado de cada pago que gana moneda sale de lo que guardaba 19: en la moneda alterna de la compañía (dólares) es su monto alterno; en otra moneda (euros), que 19 no guardaba, se recalcula del monto en bolívares con la última tasa de esa moneda hasta el día del pago; en la moneda de la compañía, en una caja en otra moneda, se deriva con la tasa de la orden. Los pagos del método en Bs. quedan sin moneda, solo con su monto local, como en 19.
- Los pagos contables del PdV que apuntaban al método archivado pasan al que sobrevive.

El plan de la fusión DEBE (MUST) quedar disponible hasta que lo lean `l10n_ve_pos_igtf` (el IGTF de cada método pasa a su moneda) y `l10n_ve_pos_mf` (el código fiscal), sea cual sea el orden en que se actualicen, y borrarse al final de la actualización; NO DEBE (MUST NOT) borrarse si el plan no se aplicó o si uno de esos módulos instalado todavía no se migró. Una instalación nueva no hace nada.

#### Scenario: Caja en bolívares con tres efectivos

- **WHEN** se actualiza una caja de 19 con «Efectivo Bs.», «Efectivo $» y «Efectivo EUR»
- **THEN** queda «Efectivo Bs.» con USD y EUR en sus monedas y una fila por moneda con los diarios de cruce de cada método viejo; los pagos de «Efectivo $» pasan a «Efectivo Bs.» en USD con su monto alterno como monto entregado, los de «Efectivo EUR» en EUR con los euros recalculados con la última tasa del euro hasta el día del pago, y «Efectivo $» y «Efectivo EUR» quedan archivados y fuera de la caja

#### Scenario: Caja en dólares

- **WHEN** se actualiza una caja de 19 cuya moneda es el dólar, con efectivo en dólares y efectivo en Bs.
- **THEN** sobrevive el efectivo en dólares, gana la moneda de la compañía, el efectivo en Bs. queda archivado con sus pagos movidos en bolívares, y los bancos sin moneda (pago móvil) ganan la moneda de la compañía

#### Scenario: Zelle

- **WHEN** la caja tiene un método de banco en divisa con diarios de cruce
- **THEN** el método sigue siendo el mismo, gana USD en sus monedas y una fila con sus diarios de cruce, y sus pagos quedan en USD

#### Scenario: Plan leído por los módulos que dependen de él

- **WHEN** la actualización aplicó el plan y `l10n_ve_pos_igtf` y `l10n_ve_pos_mf` ya se migraron, en cualquier orden
- **THEN** el plan se borra al final de la actualización

#### Scenario: Un módulo que lee el plan todavía no se migró

- **WHEN** `l10n_ve_pos_igtf` o `l10n_ve_pos_mf` está instalado y sigue en la versión de 19
- **THEN** el plan se conserva para cuando se actualice

### Requirement: Recalculo del monto alterno para todo método de pago

Cuando el monto local de una línea de pago cambia (`setAmount`), el sistema DEBE (MUST) recalcular `foreign_amount = localToForeign(amount)` para TODOS los métodos de pago, incluidos los métodos en moneda local (`_recomputeForeignFromLocal` en `payment_model.js`): el equivalente en divisa se necesita para la contabilidad dual aunque el cajero haya tecleado en bolívares.

#### Scenario: Pago en efectivo local

- **WHEN** el cajero registra un pago en bolívares, la moneda de la caja
- **THEN** la línea de pago igualmente lleva `foreign_amount` con el equivalente en moneda alterna

### Requirement: Captura de monto en divisa con liquidación exacta del adeudado

Cuando el cajero teclea el monto de una línea en la moneda en que cobra (`set_foreign_amount`), el sistema DEBE (MUST) comparar lo tecleado con el adeudado expresado en esa moneda, derivado del restante LOCAL antes de esta línea y convertido una sola vez (comparación con la precisión de esa moneda):

- Si lo tecleado es el adeudado que se muestra, el monto local de la línea DEBE (MUST) ser EXACTAMENTE el restante local, sin ida y vuelta de conversión.
- Si es mayor (sobrepago), el monto local DEBE (MUST) ser lo entregado convertido a la tasa de su moneda, nunca menos que el restante; el vuelto sale de ahí.
- Si es menor (pago parcial), el monto local es la conversión estricta de lo tecleado.

La conversión usa la tasa de la caja (y la congelada de la venta original en un reembolso) cuando la moneda es la alterna de la compañía, y la tasa de la propia moneda en otro caso (euros). En un reembolso la línea toma el signo del reembolso aunque el cajero teclee el monto sin «-». En 19 el sobrepago valía el restante más el excedente sobre el adeudado ya redondeado en la divisa, y la línea podía quedar desplazada hasta medio paso de esa moneda.

#### Scenario: Pago que cubre el total

- **WHEN** el monto en divisa tecleado es el adeudado que se muestra (dentro de la tolerancia de redondeo)
- **THEN** el monto local de la línea queda en el restante local exacto y la orden queda saldada sin residuo de céntimos

#### Scenario: Sobrepago en divisa

- **WHEN** el cliente entrega 11,30 € con la tasa del euro en 1.007,3958 y lo adeudado es menor
- **THEN** la línea vale 11.383,57 Bs (lo entregado a la tasa del euro) y el vuelto es la diferencia con lo adeudado

#### Scenario: Pago parcial en divisa

- **WHEN** el monto en divisa tecleado es menor al adeudado
- **THEN** el monto local es la conversión estricta del monto tecleado

#### Scenario: Reembolso tecleado sin signo

- **WHEN** en un reembolso el cajero teclea un monto en divisa positivo
- **THEN** la línea queda como devolución (montos negativos), no como cobro

### Requirement: Línea de pago en divisa precargada y editada en divisa

En la pantalla de pago, al agregar una línea en una moneda distinta de la de la orden y con adeudado local distinto de cero, el sistema DEBE (MUST) precargar la línea con el adeudado local convertido a esa moneda y mostrar ese monto en el teclado con el formato del idioma (en `es_VE` el punto separa miles: un «3.88» se leería como 388). Una línea en la moneda de la orden nace con el adeudado local, también con el formato del idioma.

Al teclear en una línea en otra moneda, el monto se toma en esa moneda (ver «Captura de monto en divisa con liquidación exacta del adeudado»); las líneas en la moneda de la orden siguen el comportamiento nativo. En esa rama en divisa el tope de valor máximo tiene esta forma exacta: solo actúa si ningún método de la caja es de efectivo, y compara el monto TECLEADO EN DIVISA contra el límite en MONEDA LOCAL (`remainingDue + amount de la propia línea`) con la precisión de la moneda local; al dispararse pone la línea en cero, repone en el teclado la magnitud del adeudado LOCAL con separador decimal punto y muestra el error de valor máximo. Es decir el tope mezcla monedas: con la moneda local más débil que la divisa, un sobrepago real en divisa normalmente no lo dispara.

En 19 la línea se precargaba en divisa solo para los métodos marcados «en divisa» y, si todas las líneas estaban pagadas, al teclear se agregaba una línea con el primer método de la caja; en 20 lo decide la moneda que elige el cajero y esa línea automática ya no se agrega.

#### Scenario: Agregar una línea en divisa

- **WHEN** el cajero pulsa «Efectivo», elige USD y hay adeudado pendiente
- **THEN** la línea nace con el adeudado expresado en dólares y el teclado muestra ese valor con el separador decimal del idioma

#### Scenario: Monto mayor al límite local sin efectivo configurado

- **WHEN** el cajero teclea en una línea en divisa un monto cuyo valor absoluto supera el adeudado expresado en MONEDA LOCAL y ningún método de la caja es de efectivo
- **THEN** se muestra el error de valor máximo, la línea se pone en cero y el buffer queda con la magnitud del adeudado local en formato `toString()`

#### Scenario: Sobrepago en divisa con moneda local débil

- **WHEN** el adeudado son 675 Bs (1 divisa) y el cajero teclea 10 en la línea en divisa, sin método de efectivo en la caja
- **THEN** el tope no se dispara (10 no supera 675) y la línea se procesa como sobrepago: vale los 10 entregados convertidos a la tasa de su moneda

### Requirement: Pantalla de pago en la moneda de la caja

La pantalla de pago DEBE (MUST) mostrar el total, «Restantes» y «Cambio» en la moneda de la caja aunque haya líneas en otra moneda, con el total, el restante y el cambio en moneda alterna al lado (panel «Monto Alterno» / «Restante alterno» / «Cambio alterno», que no muestra residuos negativos por redondeo). El PdV de 20 los muestra en la moneda de la primera línea de pago; 19 los mostraba en la de la caja, y así se conserva.

#### Scenario: Primera línea en dólares

- **WHEN** en una caja en bolívares el cajero agrega primero una línea en dólares que no cubre la orden
- **THEN** el total y «Restantes» siguen en bolívares, con su equivalente en moneda alterna en el panel

### Requirement: Validación de orden sin líneas de pago en cero

Al validar la orden, el sistema DEBE (MUST) rechazar la validación con un diálogo "Empty Paymentline" si alguna línea de pago tiene monto `0` o el total de la orden es `0` (`_isOrderValid` en `payment_screen.js`).

#### Scenario: Línea vacía

- **WHEN** el cajero pulsa validar con una línea de pago en cero
- **THEN** aparece el diálogo de error y la orden no se valida

### Requirement: Consulta de pagos de la orden original en reembolsos

En un reembolso, la pantalla de pago DEBE (MUST) ofrecer el botón «Ver Pagos del Origen», que consulta los pagos de las órdenes origen de las líneas reembolsadas y los muestra en la ventana «Pagos de la orden original» con su método, su etiqueta y su monto en moneda alterna. Cada pago DEBE (MUST) nombrarse como su línea de pago: el método y, si el método acepta varias monedas, la moneda en que se cobró («Efectivo Bs. USD», «Efectivo Bs. VEF»), para que el cajero sepa con qué moneda devolver. En 19, con un efectivo por moneda, el nombre del método ya lo decía.

#### Scenario: Reembolso con orden origen

- **WHEN** el cajero abre la pantalla de pago de un reembolso y pulsa el botón
- **THEN** se listan los pagos de la orden original (método, etiqueta y monto en divisa o local)

#### Scenario: Pago original en dólares con el efectivo único

- **WHEN** la venta original se cobró con «Efectivo Bs.» en dólares
- **THEN** el pago aparece como «Efectivo Bs. USD»

#### Scenario: Método de una sola moneda

- **WHEN** el pago original es de un método que acepta una sola moneda
- **THEN** aparece solo con el nombre del método

### Requirement: Botón de reembolso total en la pantalla de órdenes

La pantalla de tickets DEBE (MUST) incluir el botón "Reembolso total", que fija como cantidad a reembolsar de cada línea la cantidad aún reembolsable (`qty - refundedQty`), omitiendo las líneas ya vinculadas a una orden de reembolso destino y las que no tienen cantidad reembolsable.

#### Scenario: Orden parcialmente reembolsada

- **WHEN** el cajero pulsa "Reembolso total" sobre una orden con una línea ya parcialmente reembolsada
- **THEN** esa línea queda marcada con la cantidad restante por reembolsar y las demás con su cantidad completa

### Requirement: «Identificar cliente» exige el cliente

Un método de pago DEBE (MUST) poder marcarse «Identificar cliente» (`split_transactions`, que el núcleo de 20 eliminó y este módulo recupera). Una orden con un pago de un método marcado NO DEBE (MUST NOT) validarse sin cliente, ni en el PdV ni en el asistente de pago del backend. Además, el cruce de sus cobros en divisa se crea por pago (ver «Granularidad del cross move según split_transactions»). En 19 el núcleo, con ese flag, creaba además un pago contable por cada pago, con la cuenta del cliente; en 20 el núcleo agrupa los pagos por método y moneda.

#### Scenario: Validar en el PdV sin cliente

- **WHEN** el cajero valida una orden pagada con un método «Identificar cliente» sin haber elegido cliente
- **THEN** el PdV avisa «Se requiere un cliente para el método de pago <método>.», ofrece elegirlo y no valida la orden hasta que el cajero vuelva a validar con cliente

#### Scenario: Asistente de pago del backend sin cliente

- **WHEN** se registra desde el backend un pago con un método «Identificar cliente» en una orden sin cliente
- **THEN** se lanza un error que pide el cliente y el pago no se registra

#### Scenario: Método sin el flag

- **WHEN** el método no tiene «Identificar cliente»
- **THEN** la orden se valida sin cliente como siempre

### Requirement: El vuelto se entrega en la moneda de la caja

El vuelto de una orden DEBE (MUST) quedar en la moneda de la caja, aunque el cliente haya pagado en otra moneda, con su monto en moneda alterna calculado con la tasa de la orden. El núcleo de 20 lo da en la moneda del primer pago; 19 lo daba en bolívares, y así se conserva. El cruce del efectivo en divisa lleva solo lo que el cliente entregó.

#### Scenario: Billete de $20 para una venta de $12

- **WHEN** el cliente paga con $20 en efectivo una venta de $12,04
- **THEN** el pago de vuelto queda en bolívares, sin moneda extranjera, y su alterno es el vuelto en bolívares convertido a la tasa de la orden

### Requirement: La factura del PdV hereda la tasa de la orden

La factura generada por una orden del PdV DEBE (MUST) crearse con la tasa congelada de la orden y marcada como tasa manual, para que `l10n_ve_accountant` no la recalcule con la del día: `foreign_inverse_rate` es el multiplicador moneda principal → alterna de la orden (`foreign_currency_rate`) y `foreign_rate` su inverso, la tasa que se muestra en la factura. Cada línea de producto de la factura DEBE (MUST) llevar el precio alterno de su línea de orden; si una línea de reembolso llegó sin él, toma el de la línea original, para que la nota de crédito revierta el alterno de la factura de origen y no el de la tasa del día del reembolso.

#### Scenario: Facturación de la orden

- **WHEN** el backend factura una orden del PdV vendida a 36,5 Bs por dólar
- **THEN** la factura muestra la tasa 36,5, marcada como manual, y sus líneas el precio alterno de la venta

#### Scenario: Nota de crédito sin precio alterno en la línea

- **WHEN** se factura un reembolso cuya línea no trae precio alterno
- **THEN** la línea de la nota de crédito lleva el precio alterno de la línea original

### Requirement: El cobro de una orden facturada lleva la tasa y el alterno de sus pagos

Cuando una orden se factura, el núcleo de 20 crea por cada grupo de pagos (método y moneda) el asiento que cobra la factura (una línea del extracto del diario de efectivo o un pago contable del diario del banco) y lo concilia con la factura en el momento. Ese asiento DEBE (MUST) llevar, antes de conciliarse, la tasa con que se valoró el pago (la del primer pago del grupo que no es vuelto, como tasa manual) y en sus apuntes el alterno de los pagos que agrupa, para que no quede asiento de diferencia de cambio. Cada línea de plazo de la factura (el efectivo entregado al débito y el vuelto al crédito) DEBE (MUST) llevar el alterno de sus pagos; los céntimos que no sumen contra la venta los absorbe la línea mayor, y la cuenta por cobrar queda con alterno neto cero. Lo mismo DEBE (MUST) valer para el asiento que saca del asiento de cierre las órdenes que se facturan después de cerrar la sesión.

En 19 el cobro de la factura era un asiento del diario del PdV contra la cuenta por cobrar del PdV y el dinero pasaba al diario del método al cerrar; en 20 va directo al diario del método de pago. Los totales por cuenta no cambian.

#### Scenario: Pago de orden facturada

- **WHEN** se factura una orden cobrada con un método de banco
- **THEN** el asiento del cobro lleva la tasa del pago, marcada como manual, y en sus apuntes el alterno del pago, y la factura queda pagada sin asiento de diferencia de cambio

#### Scenario: Efectivo con vuelto

- **WHEN** se factura una orden de $12,04 pagada con $20 en efectivo
- **THEN** la línea de plazo del pago lleva $20,00 de alterno y la del vuelto $7,96, y la cuenta por cobrar queda con alterno neto cero, como en 19 (el reparto proporcional de `l10n_ve_accountant` dejaba −3,43)

#### Scenario: Factura después del cierre

- **WHEN** una orden se factura después de cerrar la sesión
- **THEN** el asiento que la saca del asiento de cierre lleva el alterno de sus pagos y la cuenta por cobrar de la factura queda con alterno neto cero

### Requirement: El efectivo en divisa se asienta en el diario de caja de su moneda

En una caja en la moneda de la compañía, cuando el diario que recibe los cobros de una moneda del método de efectivo (`cross_journal` de su configuración por moneda) es un diario de efectivo en esa moneda o en la de la compañía, distinto del diario del método, el cobro en esa moneda DEBE (MUST) asentarse en ese diario al pagar, fuera del extracto de la sesión, y esa moneda NO DEBE (MUST NOT) cruzarse al cerrar. En un diario en la moneda del pago la línea va en esa moneda, con los bolívares exactos de la venta en las columnas de la compañía; en un diario en la moneda de la compañía, en bolívares con el alterno aparte. Un reembolso sale del mismo diario.

Si ese diario es de banco, está en una tercera moneda o no está, el efectivo sigue en el diario del método y se cruza al cerrar. Las cajas en otra moneda tampoco cambian. Si se cambia el monto, la moneda o el diario de esa línea del extracto, los bolívares exactos se descartan y el asiento vuelve a la conversión del núcleo. En 19 cada efectivo tenía su diario; sin esta regla, en 20 todo el efectivo caía en la cuenta de «Efectivo Bs.».

#### Scenario: Cobro en dólares con «Efectivo $» como diario de la moneda

- **WHEN** se cobran $116 equivalentes a 4.700 Bs con el efectivo único y la fila USD tiene «Efectivo $» (diario de efectivo en dólares) como diario de cobro
- **THEN** la línea del extracto queda en «Efectivo $» por $116 con 4.700 Bs exactos en la moneda de la compañía, la factura se salda en bolívares y al cerrar no se crea cruce para los dólares

#### Scenario: Diario de cobro de banco

- **WHEN** el diario de cobro de la moneda es un banco
- **THEN** el efectivo en esa moneda queda en el diario del método y se cruza al cerrar

#### Scenario: Cobro en bolívares

- **WHEN** se cobra en bolívares con el efectivo único
- **THEN** el cobro queda en el diario del método, dentro del extracto de la sesión

### Requirement: El cobro por banco en divisa se asienta en bolívares

El pago contable de un cobro por banco en otra moneda DEBE (MUST) crearse en la moneda de la caja por el monto exacto de la venta, con su alterno aparte; la moneda en que pagó el cliente y lo que entregó quedan en el pago del PdV. El núcleo de 20 lo crea en la moneda del cliente y lo convierte a la tasa del día, lo que dejaba un asiento de diferencia de cambio al conciliar; 19 asentaba exactamente el monto de la orden.

#### Scenario: Zelle

- **WHEN** se cobran $12,04 por Zelle de una orden de 11.043,20 Bs y la tasa del día da otro monto en bolívares
- **THEN** el pago contable es de 11.043,20 Bs, la factura se concilia sin diferencia de cambio y el pago del PdV conserva USD y $12,04

### Requirement: Cierre de sesión con montos alternos en la contabilidad

El cierre de sesión de 20 arma un asiento por tipo de orden (ventas, reembolsos) con una línea de plazo por método de pago y moneda, y crea y concilia por cada línea el asiento que la salda. El asiento de cierre DEBE (MUST) llevar la tasa de la configuración de la caja; cada línea de plazo DEBE (MUST) llevar la suma de los alternos de los pagos que agrupa, y las demás líneas se reparten el alterno para que el asiento cuadre en moneda alterna. Los asientos que saldan esas líneas DEBEN (MUST) llevar en sus apuntes el alterno de sus pagos, y los pagos contables de banco, la tasa de la configuración. Aunque la tasa haya cambiado entre la venta y el cierre, NO DEBE (MUST NOT) quedar asiento de diferencia de cambio, como en 19.

#### Scenario: Efectivo y banco en la misma sesión

- **WHEN** se cierra una sesión con pagos en efectivo y por banco
- **THEN** cada línea de plazo del asiento de cierre lleva el alterno de los pagos de su método, y el asiento que la salda el mismo alterno

#### Scenario: Tasa movida después de la venta

- **WHEN** la tasa del día cambia entre la venta y el cierre
- **THEN** el cierre no crea asiento de diferencia de cambio

### Requirement: Nota de cierre y resumen del efectivo en la sesión

La nota que el cajero escribe en la ventana de cierre DEBE (MUST) guardarse en la sesión en toda caja (el PdV de 20 no la enviaba), la última que escribe gana y una vacía la borra; una sesión cerrada conserva la suya y un usuario sin acceso al PdV NO DEBE (MUST NOT) poder escribirla. Al cerrar una caja con método de efectivo, la sesión DEBE (MUST) publicar una vez en su historial, como en 19, la diferencia, el efectivo esperado y el contado de la caja y, si la hay, la nota; la apertura no publica este mensaje. Los módulos que guardan parte del efectivo aparte (un cajón secundario) lo descuentan, para que el mensaje muestre el conteo de la caja.

La ventana de cierre es la nativa de 20: el efectivo aparece en una sola cifra en bolívares (19 mostraba un total en bolívares por método).

#### Scenario: Cierre con nota

- **WHEN** el cajero escribe una nota en la ventana de cierre y cierra la sesión
- **THEN** la sesión guarda la nota y su historial muestra la diferencia, el esperado, el contado y la nota

#### Scenario: Cierre sin nota

- **WHEN** el cajero cierra sin escribir nota
- **THEN** el mensaje muestra la diferencia, el esperado y el contado, sin renglón de nota

### Requirement: Cruces de compensación de los cobros en divisa

Al cerrar la sesión, por cada método de pago y cada moneda distinta de la de la orden con que se cobró en esa sesión, el sistema DEBE (MUST) crear en el diario de cruce de esa moneda (`cross_account_journal` de la configuración por moneda) asientos EN BORRADOR que trasladan los cobros desde la cuenta del método hacia el diario que recibe esa moneda (`cross_journal`). Cada asiento lleva el alterno y la tasa de los pagos, y una referencia que identifica la sesión (o la orden y el pago, ver la granularidad); el número lo asigna el diario al contabilizarlo. Las líneas del diario de cobro van en la moneda de ese diario: si es el de la moneda del pago (euros), con lo que entregó el cliente.

- Efectivo: el asiento va entre la cuenta transitoria del diario del método y la del diario de cobro (las que usan las entradas y salidas de efectivo): en una venta debita la del método y acredita la del diario de cobro; a la inversa en una devolución.
- Banco: de la cuenta de pendientes del método (o la del diario, si no tiene) a la cuenta de pagos entrantes o salientes del diario de cobro, según el signo.
- No se cruzan los métodos a crédito, las monedas sin fila en la configuración del método o sin alguno de los dos diarios (se omiten en silencio) ni el efectivo de una moneda que ya se asentó en su diario de caja (ver «El efectivo en divisa se asienta en el diario de caja de su moneda»).

La sesión NO DEBE (MUST NOT) abrirse si a un cruce configurado le faltan sus cuentas: el error lista cada método, su moneda y la cuenta que falta. Si en el cierre falta una cuenta transitoria del efectivo, el cruce se omite con un aviso en el registro; si falta otra cuenta de las líneas, el cierre da un error legible en lugar de fallar en la base de datos. Un cliente de otra compañía no va en el encabezado del asiento (las líneas lo conservan). En 19 se cruzaban los métodos marcados «en divisa», con sus diarios en el método; en 20 se cruza por moneda del pago.

#### Scenario: Cobros en divisa con los diarios configurados

- **WHEN** se cierra una sesión con cobros en USD por Zelle cuya fila USD tiene los dos diarios
- **THEN** se crea un asiento borrador en el diario de cruce que acredita la cuenta de pendientes de Zelle y debita la cuenta de pagos entrantes del diario de cobro (a la inversa para un reembolso)

#### Scenario: Configuración incompleta

- **WHEN** la fila de la moneda no tiene diario de cruce o diario de cobro, o el método no tiene fila para esa moneda
- **THEN** no se crea ningún cruce para esa moneda y el cierre no falla

#### Scenario: Cobros en la moneda de la caja

- **WHEN** la sesión solo tiene cobros en bolívares
- **THEN** no se crea ningún cruce

#### Scenario: Cuenta faltante al abrir

- **WHEN** se abre una sesión cuyo método tiene en una moneda los dos diarios de cruce pero al diario de cobro le falta la cuenta que usará el cruce
- **THEN** la sesión no se abre y el error nombra el método, la moneda y la cuenta

### Requirement: Granularidad del cross move según split_transactions

La granularidad de los cross moves DEBE (MUST) seguir «Identificar cliente» (`split_transactions`) del método: con el flag activo se crea un asiento por cada pago (referenciando orden y pago); sin él, un único asiento por método, moneda y sesión, con una pata para los cobros (montos positivos) y otra para las devoluciones (montos negativos), cada una neteada por separado. Solo NO DEBE (MUST NOT) crearse cuando los netos en bolívares, en moneda alterna y en la moneda del pago son todos cero.

#### Scenario: Método identificando cliente

- **WHEN** el método tiene «Identificar cliente» activo y la sesión registró tres pagos en USD con él
- **THEN** se crean tres asientos borrador, cada uno con la referencia de su pago

#### Scenario: Venta de hoy y reembolso a una tasa vieja

- **WHEN** el método no identifica cliente y la sesión tiene una venta en USD de hoy y un reembolso en USD de una venta vendida a otra tasa
- **THEN** se crea un solo asiento con cuatro líneas, una pata por la venta y otra por el reembolso, y el cierre no falla aunque el neto en bolívares y el neto en dólares tengan signos opuestos

#### Scenario: Neto cero en bolívares con divisas de diferencia

- **WHEN** las ventas y devoluciones en USD de un método se anulan en bolívares pero no en dólares
- **THEN** el asiento se crea y las divisas pasan al diario de cobro

#### Scenario: Neto cero en todas las monedas

- **WHEN** las ventas y devoluciones del método se anulan en bolívares, en moneda alterna y en la moneda del pago
- **THEN** no se crea ningún asiento para ese método y moneda

### Requirement: Reescritura de totales de las órdenes al cerrar la sesión

Al cerrar la sesión (por la ventana del PdV o por el botón del backend, que en 20 pasan por el mismo cierre), después del cierre del núcleo y de los cruces, el sistema DEBE (MUST) reescribir el total de TODAS las órdenes de la sesión, sin filtrar por estado, y el subtotal de cada una de sus líneas redondeados a 2 decimales con `round()` de Python — NO con el redondeo de la moneda ni con el método de redondeo de la caja. Si el cierre del núcleo no termina, no se reescribe nada.

Esta escritura ocurre después de que el core ya generó los asientos de cierre, así que los asientos no se recalculan a partir de los nuevos valores.

#### Scenario: Cierre de una sesión con órdenes

- **WHEN** un usuario cierra una sesión con órdenes ya facturadas, desde el PdV o desde el backend
- **THEN** cada orden queda con `amount_total` y `price_subtotal` de sus líneas redondeados a 2 decimales con `round()` de Python, y los asientos contables ya creados no se ajustan

#### Scenario: Moneda con precisión distinta de 2 decimales

- **WHEN** la moneda de la caja tiene una precisión distinta de dos decimales
- **THEN** el cierre igualmente fuerza dos decimales, porque `_apply_rounding` ignora la moneda

### Requirement: Reasignación de los xml_ids de grupos del módulo antiguo al instalar

El módulo DEBE (MUST) ejecutar el `pre_init_hook` `pre_init_hook` → `reassign_xml_groups_ids`, que por SQL reasigna en `ir_model_data` todas las filas con `module = 'binaural_pos'` y `name` que empiece por `group_` al módulo `l10n_ve_pos`, para que los grupos que ya existían con el nombre viejo del módulo no se dupliquen ni se pierdan las asignaciones de usuarios.

#### Scenario: Instalación sobre una base con el módulo antiguo

- **WHEN** se instala `l10n_ve_pos` en una base donde los grupos fueron creados por `binaural_pos`
- **THEN** los `ir.model.data` de esos grupos pasan a pertenecer a `l10n_ve_pos` antes de cargar los datos del módulo, y los grupos se actualizan en vez de crearse de nuevo

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

El sistema DEBE (MUST) enviar al PdV solo la moneda de la compañía, la de la caja, la alterna y las que aceptan los métodos de pago de la caja, con su tasa inversa y con la moneda de la compañía en primera posición. Las monedas de las listas de precios que no están entre esas NO DEBEN (MUST NOT) cargarse. En 19 no se cargaban las monedas de los métodos, porque cada moneda tenía su método.

#### Scenario: Compañía con moneda alterna

- **WHEN** se abre una caja de una compañía con moneda alterna configurada
- **THEN** al frontend llegan únicamente esas monedas, con la de la compañía primero

#### Scenario: Efectivo que acepta euros

- **WHEN** el método de efectivo de la caja acepta EUR y ni la compañía ni la caja ni la alterna son EUR
- **THEN** el euro también llega al PdV, con su tasa, para cobrar en él

### Requirement: Permisos para cambiar cantidad y precio en la caja

El módulo DEBE (MUST) restringir los botones de cantidad y precio del numpad a los usuarios con los grupos `l10n_ve_pos.group_change_qty_on_pos_order` y `l10n_ve_pos.group_change_price_on_pos_order` respectivamente: el loader de `res.users` expone los flags como `_can_change_qty_on_pos_order` / `_can_change_price_on_pos_order` (calculados con `has_group` en servidor) y `ProductScreen.getNumpadButtons` deshabilita el botón correspondiente cuando el flag es falso. Ambos grupos se definen sin `privilege_id` para comportarse como permisos independientes.

#### Scenario: Cajero sin permiso de precio

- **WHEN** un usuario sin el grupo de cambio de precio abre la pantalla de productos
- **THEN** el botón "price" del numpad aparece deshabilitado

#### Scenario: Cajero con ambos grupos

- **WHEN** el usuario pertenece a ambos grupos
- **THEN** los botones de cantidad y precio funcionan normalmente

### Requirement: Visibilidad y orden de productos según disponibilidad

Con el flag de compañía `pos_show_just_products_with_available_qty` activo, el sistema DEBE (MUST) ordenar el `product.product` cargado al PdV por `qty_available` descendente, y la cuadrícula del PdV, también al buscar, NO DEBE (MUST NOT) mostrar los almacenables sin ninguna variante con `qty_available` positiva (`ProductTemplate.canBeDisplayed`). Lo no almacenable se muestra siempre. `qty_available` se calcula en la ubicación de origen de la caja y sus hijas, la que valida "Cantidad en 0".

#### Scenario: Flag activo

- **WHEN** la compañía activa el flag y se abre la caja
- **THEN** los productos llegan ordenados por disponibilidad descendente, computada contra la ubicación de origen de la caja

#### Scenario: Flag activo y almacenable sin stock en la ubicación de origen de la caja

- **WHEN** la compañía activa el flag y un producto almacenable disponible en el PdV tiene stock a mano 0 o negativo en la ubicación de origen de la caja
- **THEN** el producto no aparece en la cuadrícula ni en la búsqueda del PdV

#### Scenario: Stock solo en otro almacén

- **WHEN** el flag está activo y el producto tiene stock en otro almacén de la compañía pero no en el de la caja
- **THEN** el PdV recibe `qty_available` 0 para ese producto y no lo muestra

#### Scenario: Stock en otra ubicación del almacén de la caja

- **WHEN** el flag está activo y el producto tiene stock en una ubicación del almacén de la caja que no es la de origen ni hija de ella
- **THEN** el PdV recibe `qty_available` 0 para ese producto y no lo muestra, igual que "Cantidad en 0" no lo dejaría vender

#### Scenario: Alguna variante con stock

- **WHEN** el flag está activo y al menos una variante del producto tiene stock a mano positivo en la ubicación de origen de la caja
- **THEN** el producto aparece en la cuadrícula

#### Scenario: Producto no almacenable

- **WHEN** el flag está activo y el producto es un servicio, un consumible sin control de stock o un combo
- **THEN** el producto aparece aunque no tenga stock

#### Scenario: Flag apagado

- **WHEN** la compañía no activa el flag
- **THEN** los productos almacenables sin stock aparecen en la cuadrícula y el bloqueo de vender sin stock depende de "Cantidad en 0" (`amount_to_zero`)

### Requirement: Existencia disponible en la tarjeta de producto

Con `pos_show_free_qty` activo en la compañía, la tarjeta de producto DEBE (MUST) mostrar la cantidad disponible obtenida en vivo vía `getProductInfo` (con debounce), leyendo `available_quantity` del primer almacén reportado.

#### Scenario: Consulta de stock de la tarjeta

- **WHEN** se renderiza la tarjeta de un producto con el flag activo
- **THEN** se consulta la información del producto y se muestra la cantidad disponible (0 si la consulta falla)

### Requirement: Endpoints de validación de stock del PdV

El controlador DEBE (MUST) exponer las rutas JSON `/validate_products_order` y `/validate_products_in_warehouse` (ambas `auth="public"`):

- `/validate_products_order` recorre los ids recibidos y devuelve `msg_error` con el nombre del producto en cuanto una PLANTILLA (`product_tmpl_id`) con `is_storable` y `type == "consu"` tiene `qty_available` GLOBAL (sin acotar por almacén) menor a la cantidad pedida. Si se llama sin `lines` o sin `qty` no devuelve nada (`None`).
- `/validate_products_in_warehouse` suma la `available_quantity` de los quants `on_hand` de la plantilla que pertenecen al almacén del `picking_type_id` recibido y distingue DOS fallos con tratamiento distinto:
  - Stock insuficiente en ese almacén (el producto sí está en él): devuelve `msg_error` de inmediato, SIN importar el valor de `sell_kit_from_another_store`.
  - Producto sin quants o sin presencia en el almacén de la caja: se acumula en una lista y solo se convierte en `msg_error` al final `if not sell_kit_from_another_store`.

Es decir, `sell_kit_from_another_store` exime únicamente los productos ausentes del almacén de la caja; nunca el stock insuficiente.

Ni en 19 ni en 20 las llama ningún JS del PdV (son código heredado de 17). El bloqueo por stock antes del pago con "Cantidad en 0" lo hace `pos.config.check_stock_availability` (ver el requirement «"Cantidad en 0" bloquea el pago sin stock a mano»), con otra semántica: stock a mano de la ubicación origen de la caja, sin kits de otra tienda.

#### Scenario: Stock insuficiente en el almacén de la caja

- **WHEN** se llama `/validate_products_in_warehouse` con una cantidad mayor a la disponible en el almacén del picking type, con `sell_kit_from_another_store` verdadero
- **THEN** la respuesta incluye igualmente un `msg_error` indicando el producto y el almacén

#### Scenario: Producto ausente del almacén de la caja con la venta cruzada habilitada

- **WHEN** el producto no tiene quants en el almacén del picking type y se pasa `sell_kit_from_another_store` verdadero
- **THEN** la respuesta vuelve con `msg_error` en `False` y la venta se permite

### Requirement: "Cantidad en 0" bloquea el pago sin stock a mano

Con `amount_to_zero` activo en la caja, al pulsar "Pago" (o al validar con el pago rápido) el PdV DEBE (MUST) comparar la cantidad pedida por producto almacenable (suma de líneas positivas) contra el stock a mano de la ubicación origen de la caja (`pos.config.check_stock_availability`) y, si alguna la supera, mostrar "Stock insuficiente" con el detalle y no pasar a la pantalla de pago. Lo reservado por otras órdenes no reduce el stock a comparar.

#### Scenario: Stock a mano suficiente aunque esté reservado por otra orden

- **WHEN** hay 8 a mano, otra orden confirmada reservó 7 y la orden del PdV lleva 7
- **THEN** el PdV pasa a la pantalla de pago

#### Scenario: Stock a mano insuficiente

- **WHEN** hay 1 a mano y la orden del PdV lleva 7
- **THEN** se muestra "Stock insuficiente" con "pedido 7, a mano 1" y no se abre la pantalla de pago ni se imprime en la MF

#### Scenario: Check apagado o producto no almacenable

- **WHEN** la caja no tiene `amount_to_zero`, o el producto es servicio/consumible no almacenable
- **THEN** no se valida stock

#### Scenario: Pago rápido

- **WHEN** la caja usa el pago rápido y la orden lleva más de lo que hay a mano
- **THEN** se muestra "Stock insuficiente" y la orden no se valida ni se imprime en la MF

#### Scenario: Producto que ya no existe

- **WHEN** la orden trae el id de un producto borrado después de que la caja lo cargó
- **THEN** ese producto se omite y el resto de la orden se valida normalmente

### Requirement: Formulario reducido de contacto exclusivo del PdV

El PdV DEBE (MUST) abrir la creación/edición de clientes con la vista `l10n_ve_pos.view_partner_form_pos`, derivada de `base.view_partner_form` en `mode="primary"` (hereda los campos de `l10n_ve_contact` y `l10n_ve_location` ya combinados) que elimina botones inteligentes, foto, sitio web, idioma, etiquetas, propiedades y el notebook completo, y sustituye el campo `function` por `barcode`. La acción que el PdV abre para el cliente (la que devuelve `res.partner.action_open_partner_view`) apunta a esa vista y lleva en el contexto `l10n_ve_pos_partner_defaults`, sin modificar el formulario de Contactos del backoffice. Sin esto el PdV de 20 abriría su propio formulario, que no trae los campos de `l10n_ve_contact` ni de `l10n_ve_location`. Al crear un cliente desde la búsqueda, el núcleo de 20 prellena el nombre (o el teléfono, si lo buscado parece uno) con lo buscado; en 19 no lo hacía.

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

El PdV DEBE (MUST) mostrar como «Tasa BCV», en el resumen de la orden y en la pantalla de órdenes, la tasa operativa normalizada a la semántica "1 divisa = X local" (si la tasa cruda es menor a 1 se muestra su inverso), formateada con la precisión decimal `Tasa`, junto al total de productos y al total e impuestos en moneda alterna. Una orden ya validada, abierta desde la pantalla de órdenes, muestra la tasa a la que se vendió, no la del día. Si no hay tasa disponible se muestra "N/D" y se alerta una única vez por orden con un diálogo pidiendo configurar la tasa.

#### Scenario: Tasa cruda invertida

- **WHEN** la configuración expone la tasa como factor menor a 1
- **THEN** en pantalla se muestra `1/tasa` con la precisión de `Tasa`

#### Scenario: Tasa faltante

- **WHEN** no existe tasa operativa
- **THEN** se muestra "N/D" y aparece la alerta "Tasa de conversión faltante" una sola vez

### Requirement: Recibo y pantallas con totales en moneda alterna

El recibo DEBE (MUST) llevar lo que la localización le agrega en 19, tanto el que imprime el PdV como el que arma el servidor (reimpresión desde el backend, kiosco): en cada línea la letra de alícuota (G)/(E) y el monto en moneda alterna junto al local; un renglón «TOTAL» en moneda alterna debajo del total, sin el desglose de impuestos; la dirección del cliente y su RIF sin etiqueta. Un pago en una moneda distinta de la de la caja DEBE (MUST) imprimirse con el método y la moneda pagada y el monto en la moneda de la caja («Efectivo Bs. (USD)  36.106,20 Bs.F»); los pagos en la moneda de la caja se imprimen como en el núcleo. El vuelto DEBE (MUST) imprimirse en la moneda de la caja, en su renglón, y NO DEBE (MUST NOT) aparecer además como una línea de pago negativa. En 19, con un efectivo por moneda, el pago salía como «Efectivo $  36.106,20».

La pantalla de pago muestra el total alterno adeudado debajo del total, y la pantalla final del pago («Pago exitoso», la nativa de 20) muestra debajo del monto cobrado el total en moneda alterna, salvo que ese monto ya esté en la moneda alterna. Esa pantalla muestra el monto en la moneda del primer pago (núcleo); en 19 mostraba bolívares y alterno.

#### Scenario: Línea gravada

- **WHEN** se imprime el recibo de una orden con un producto con IVA
- **THEN** la línea muestra (G) y su monto local seguido de « / » y el monto en moneda alterna, y el recibo trae el renglón «TOTAL» en moneda alterna

#### Scenario: Línea exenta

- **WHEN** la línea no tiene impuestos o su primer impuesto es de 0 %
- **THEN** la línea muestra (E)

#### Scenario: Pago en dólares con vuelto

- **WHEN** se imprime el recibo de una orden pagada con dólares en efectivo y con vuelto
- **THEN** el pago sale como «Efectivo Bs. (USD)» con su monto en bolívares, el vuelto sale en bolívares en su renglón y no hay una línea de pago por el vuelto

#### Scenario: Reimpresión desde el backend

- **WHEN** se reimprime desde el backend el recibo de una orden del PdV
- **THEN** trae la letra de alícuota, los montos y el total en moneda alterna y los pagos con su moneda, igual que el impreso en la caja

#### Scenario: Residuo negativo por redondeo

- **WHEN** el restante alterno calculado es un residuo negativo por debajo del redondeo de la moneda
- **THEN** el panel de estado de la pantalla de pago muestra 0 y no un valor negativo

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

### Requirement: La tasa de la caja es la del día del usuario

`pos.config._compute_rate` DEBE (MUST) buscar la tasa de `fields.Date.context_today` y no la de `fields.Date.today()`. Como esa búsqueda usa `raise_if_not_found=False`, usar la fecha UTC dejaba la caja con tasa `0` sin avisar después de las 8 pm de Caracas.

#### Scenario: Caja consultada a las 8:30 pm en Caracas

- **WHEN** se calcula la tasa de la caja a las 00:30 UTC del día siguiente y hay tasa del día del usuario
- **THEN** `foreign_rate` toma la tasa del día del usuario y no queda en 0

### Requirement: "Permitir crear productos" por caja

`pos.config` DEBE (MUST) tener `allow_product_creation_in_pos` ("Permitir crear productos"), apagado por defecto y editable desde Ajustes. Apagado, el PdV DEBE (MUST) ocultar "Crear producto" del menú y "Crear manualmente" de la pantalla de productos vacía, y `PosStore.editProduct()` sin producto NO DEBE (MUST NOT) abrir el formulario. Solo un `true` explícito la enciende.

#### Scenario: Creación permitida

- **WHEN** la caja tiene "Permitir crear productos" encendido y el usuario tiene permiso para crear productos
- **THEN** el menú del PdV muestra "Crear producto" y abre el formulario de producto nuevo

#### Scenario: Creación apagada

- **WHEN** la caja tiene "Permitir crear productos" apagado
- **THEN** el menú no muestra "Crear producto", la pantalla de productos vacía no muestra "Crear manualmente" y `editProduct()` sin producto no abre nada

#### Scenario: Editar un producto existente con la creación apagada

- **WHEN** la caja tiene "Permitir crear productos" apagado y el cajero edita un producto existente
- **THEN** se abre el formulario de edición como siempre

#### Scenario: Caja cargada antes de actualizar el módulo

- **WHEN** el PdV trae `pos.config` de su caché sin el campo (`undefined`)
- **THEN** la creación se trata como no permitida

#### Scenario: Cajas existentes al actualizar

- **WHEN** se actualiza `l10n_ve_pos` en una base con cajas creadas antes
- **THEN** todas quedan con "Permitir crear productos" apagado hasta que se encienda en Ajustes

### Requirement: Stock actual al abrir la caja con "Mostrar solamente los productos disponibles"

Con el flag activo, `pos.session.load_data` DEBE (MUST) cargar `product.template` y `product.product` sin el filtro por `write_date` de la carga incremental, porque un movimiento de stock no lo cambia: una sesión nueva o la entrada desde el backend traen el stock actual aunque la caja tenga caché. F5 con la sesión abierta no consulta al servidor: para eso lo recomendado es "Volver a cargar datos" → "Limitado".

#### Scenario: Stock cambiado con la caja ya cargada

- **WHEN** el flag está activo, la caja cargó un producto almacenable y después su stock cambia en la ubicación de origen de la caja (se repone o se agota) sin que cambie el producto
- **THEN** al abrir una sesión nueva o entrar desde el backend el producto aparece o desaparece según el stock actual

#### Scenario: F5 con la sesión abierta

- **WHEN** el flag está activo, la sesión sigue abierta y se repone el stock de un producto oculto
- **THEN** tras F5 sigue oculto, y aparece tras "Volver a cargar datos" → "Limitado", que vacía la caché del navegador igual que "Completo" y recarga hasta `point_of_sale.limited_product_count` plantillas

#### Scenario: Flag apagado

- **WHEN** la compañía no activa el flag y la caja abre con caché
- **THEN** la carga incremental conserva el filtro por `write_date` del core y solo reenvía los productos modificados

### Requirement: El cross move se fecha en el día del usuario

`_create_cross_move` DEBE (MUST) fechar el asiento en el día del usuario (`fields.Date.context_today`) cuando recibe un Datetime en UTC (`stop_at` de la sesión o `create_date` del pago), y no truncarlo al día UTC. Desde las 8 pm de Caracas el día UTC ya es el siguiente, todavía sin tasa, y `l10n_ve_accountant` detenía el cierre de la sesión.

#### Scenario: Cierre a las 8:30 pm de Caracas con un método que no identifica cliente

- **WHEN** la sesión se cierra con `stop_at` a las 00:30 UTC del día siguiente y solo hay tasa del día del usuario
- **THEN** el cross move del método se crea con la fecha del día del usuario, sin pedir la tasa del día UTC

#### Scenario: Pago registrado a las 8:30 pm de Caracas con un método que identifica cliente

- **WHEN** el pago se registró a las 00:30 UTC del día siguiente y solo hay tasa del día del usuario
- **THEN** el cross move de ese pago se crea con la fecha del día del usuario
