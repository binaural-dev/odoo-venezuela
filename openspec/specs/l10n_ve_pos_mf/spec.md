# l10n_ve_pos_mf

## Purpose

Integra las impresoras fiscales TFHKA con el Punto de Venta vía Web Serial API, usando el driver compartido de `l10n_ve_mf_base` (sin stack IoT). Cubre la configuración fiscal de la caja, la construcción del payload fiscal de la orden PdV, la impresión bloqueante durante la validación de pago, la impresión de pedidos que quedaron sin facturar, la reimpresión, los reportes X/Z con su sincronización en Odoo, el cierre de sesión condicionado al Reporte Z y el Libro de Ventas por Reporte Z. Extiende `pos.config`, `pos.order`, `pos.session`, `pos.payment.method`, `account.tax`, `account.move`, `res.users` y `res.config.settings`, y agrega el wizard `wizard.sales.book`. Depende de `point_of_sale`, `l10n_ve_pos` (helpers de moneda extranjera y bloque de ajustes) y `l10n_ve_mf_base` (driver, protocolo y parser de estado). Puede convivir con `l10n_ve_account_mf` (o `l10n_ve_iot_mf`) compartiendo los campos fiscales de `account.move` y encadenando `report_z`.

## Requirements

### Requirement: Configuración de la máquina fiscal por caja

`pos.config` DEBE (MUST) exponer la configuración fiscal de la caja: `serial_machine`, `flag_21` (selección `00`/`01`/`02`/`30`, requerido, default `00`), `traditional_line`, `has_cashbox` (default `True`), `access_button_mf` (default `True`), `message_in_head`, `enable_auto_sync`, `auto_sync_interval` (default 60) y `mf_skip_invoice_pdf` (default `True`). Todos DEBEN (MUST) viajar al frontend del PdV mediante `_load_pos_data_fields`, que los agrega a la lista del core salvo que el core devuelva `[]` (que significa "todos los campos"). `pos_access_button_mf` y `message_in_head` son editables desde el bloque de ajustes de `l10n_ve_pos`.

#### Scenario: Flag 21 configurado en la caja

- **WHEN** la caja tiene `flag_21 = "30"` y se construye el payload de una orden
- **THEN** el payload trae `flag_21 = "30"` y el driver de `l10n_ve_mf_base` formatea montos y cantidades con esa configuración

#### Scenario: El core ya carga todos los campos

- **WHEN** `_load_pos_data_fields` del core devuelve una lista vacía
- **THEN** no se agrega ningún campo fiscal y la lista vacía se devuelve tal cual

### Requirement: Código fiscal del método de pago del PdV

`pos.payment.method` DEBE (MUST) tener el campo `code_fiscal_printer` (Char de 2 caracteres, default `01`), editable en el formulario del método de pago y cargado siempre en el PdV vía `_load_pos_data_fields`. Ese código es el que se envía a la impresora como método de pago TFHKA.

#### Scenario: Método de pago mapeado

- **WHEN** un método de pago del PdV tiene `code_fiscal_printer = "20"` y se cobra con él
- **THEN** la línea de pago del payload lleva `payment_method_code = "20"`

### Requirement: Código fiscal del impuesto y resolución del código de la línea

`account.tax` DEBE (MUST) tener el campo `fiscal_code` (Integer, default 0, editable en el formulario de impuesto) y cargarse en el PdV vía `_load_pos_data_fields`. Al construir la línea fiscal, el código DEBE (MUST) tomarse del PRIMER impuesto de la línea (`line.tax_ids[0].fiscal_code`), eliminando un prefijo `t` si existe; una línea sin impuestos usa `"0"` (exento).

#### Scenario: Línea sin impuestos

- **WHEN** una línea de la orden no tiene impuestos asociados
- **THEN** su `fiscal_code` en el payload es `"0"`

#### Scenario: Línea con varios impuestos

- **WHEN** una línea tiene dos impuestos y el primero tiene `fiscal_code = 1`
- **THEN** el payload usa `"1"` e ignora el resto de impuestos

### Requirement: Construcción del payload fiscal de la orden PdV

`get_data_invoice(order)` DEBE (MUST) construir el payload fiscal con: la compañía; `flag_21`, `traditional_line` y `has_cashbox` de la caja (este último solo verdadero si además la orden se pagó con efectivo, `order.isPaidWithCash()`); el cliente (`prefix_vat` + `vat` concatenados, nombre normalizado, `street` como dirección y `phone` o `mobile` como teléfono) cuando la orden tiene partner; las líneas informativas `info`; y una línea por cada línea de la orden con `price_unit`, `discount` de línea, `quantity` en valor absoluto, nombre normalizado sin el prefijo `[código]` del `display_name`, `code` = `default_code` del producto y `tax` = código fiscal. Las notas de cliente de cada línea DEBEN (MUST) agregarse a `info`, una entrada por salto de línea.

#### Scenario: Orden con cliente y nota

- **WHEN** se prepara una orden con partner y una línea con nota de cliente de dos renglones
- **THEN** el payload trae `partner_id` con RIF, nombre, dirección y teléfono, y `info` incluye dos entradas adicionales con los renglones de la nota

#### Scenario: Gaveta solo con efectivo

- **WHEN** la caja tiene `has_cashbox = True` pero la orden no se pagó con efectivo
- **THEN** el payload trae `has_cashbox = false` y el driver no envía el comando de apertura de gaveta

### Requirement: Líneas informativas de operador y referencia del pedido

`aditionalInfo(order)` DEBE (MUST) devolver las líneas informativas del ticket con el operador (`OPERADOR: <nombre del cajero>`) cuando hay cajero, y la referencia del pedido (`PEDIDO: <pos_reference o uuid>`) cuando existe.

#### Scenario: Orden con cajero y referencia

- **WHEN** hay un cajero activo y la orden tiene `pos_reference`
- **THEN** `info` comienza con `OPERADOR: <nombre>` seguido de `PEDIDO: <pos_reference>`

### Requirement: Normalización de textos hacia la impresora

`normalizeProductName(text)` DEBE (MUST) normalizar el texto en NFKD, eliminar los diacríticos, reemplazar todo carácter no alfanumérico por espacio, colapsar espacios consecutivos y recortar los extremos, devolviendo cadena vacía cuando la entrada es vacía. Se aplica al nombre del cliente y al nombre del producto antes de enviarlos a la impresora.

#### Scenario: Nombre con acentos y símbolos

- **WHEN** se normaliza `"Café & Té (500g)"`
- **THEN** el resultado es `"Cafe Te 500g"`

### Requirement: Montos en moneda nacional o extranjera

El payload DEBE (MUST) expresar los montos en la moneda base cuando la moneda del PdV es `VEF` o `VES` (usando `price_unit` y `payment.amount`), y en caso contrario DEBE (MUST) usar los helpers de moneda extranjera de `l10n_ve_pos` (`get_foreign_unit_price` en la línea, `get_foreign_amount` en el pago y `get_foreign_total_with_tax` en la orden), tomando `decimal_places` y `rounding` de `config.foreign_currency_id` con fallback a la moneda del PdV. Los montos de pago DEBEN (MUST) redondearse con ese `rounding`.

#### Scenario: PdV en moneda extranjera

- **WHEN** la moneda del PdV no es VEF/VES y la línea tiene precio en esa moneda
- **THEN** el payload usa `line.get_foreign_unit_price()` como `price_unit` y el redondeo de la moneda extranjera

#### Scenario: PdV en bolívares

- **WHEN** la moneda del PdV es `VES`
- **THEN** el payload usa `line.price_unit` y `payment.amount` sin conversión

### Requirement: Filtrado de líneas de pago válidas

Las líneas de pago del payload DEBEN (MUST) descartar todo pago sin `code_fiscal_printer` y, según el tipo de documento, conservar solo los montos con signo coherente: positivos para `out_invoice` y negativos para `out_refund` (comparando con cero mediante el redondeo y las posiciones decimales de la moneda). Si tras el filtrado no queda ninguna línea de pago, `get_data_invoice` DEBE (MUST) devolver `valid: false` con el mensaje correspondiente y no se imprime nada.

#### Scenario: Método de pago sin código fiscal

- **WHEN** un pago usa un método sin `code_fiscal_printer`
- **THEN** ese pago se excluye del payload

#### Scenario: Ningún pago válido

- **WHEN** ninguna línea de pago supera el filtrado
- **THEN** el resultado es `valid: false` con el mensaje de que no hay líneas de pago válidas para la máquina fiscal

### Requirement: Detección de nota de crédito y factura afectada

El tipo de documento DEBE (MUST) ser `out_refund` cuando el total de la orden es negativo o cuando alguna línea tiene `refunded_orderline_id`, y `out_invoice` en caso contrario. Para `out_refund` los datos de la orden original DEBEN (MUST) resolverse en este orden de prioridad: el registro en memoria (`refunded_orderline_id.order_id` con `mf_invoice_number`), el historial local `LocalOrderHistory.getByUid` (offline) y por último la llamada RPC `pos.order.get_order_by_uid`. Si no se obtiene la orden original, o si esta no tiene `mf_invoice_number`, DEBE (MUST) devolverse `valid: false` con el motivo. Con los datos resueltos se construye `invoice_affected` con `number` (número fiscal), `serial_machine` (`fiscal_machine`) y `date` (fecha de la orden formateada en locale `es-ES`).

#### Scenario: Devolución de un pedido facturado en memoria

- **WHEN** la orden tiene una línea con `refunded_orderline_id` cuyo pedido original ya está cargado y tiene `mf_invoice_number`
- **THEN** el tipo es `out_refund` y `invoice_affected` se arma con el número, el serial y la fecha del pedido original sin consultar al servidor

#### Scenario: Pedido original sin número fiscal

- **WHEN** la orden original recuperada no tiene `mf_invoice_number`
- **THEN** el resultado es `valid: false` indicando que la orden original no tiene número de factura fiscal registrado

#### Scenario: Pedido original no recuperable

- **WHEN** ni el registro en memoria, ni el historial local, ni el RPC devuelven la orden original
- **THEN** el resultado es `valid: false` indicando que no se pudo recuperar la factura original

### Requirement: Prorrateo de los pagos de la nota de crédito

Cuando el documento es `out_refund` y la orden no aporta líneas de pago válidas pero la orden original sí trae `payment_lines`, el payload DEBE (MUST) reconstruir los pagos prorrateando el total a devolver entre los métodos de la orden original en proporción a sus montos, asignando al último método el remanente restante, sin que ningún monto exceda el remanente disponible, y emitiendo todos los montos en negativo. Los métodos sin código fiscal o con monto no positivo se descartan antes del prorrateo.

#### Scenario: Devolución total de una orden con dos métodos

- **WHEN** la orden original se pagó 30% con el método `01` y 70% con el método `08` y se devuelve el total
- **THEN** el payload trae dos líneas negativas con esos códigos, proporcionales a los montos originales, y la última absorbe el remanente por redondeo

#### Scenario: Orden original sin pagos recuperables

- **WHEN** la orden original no trae `payment_lines` utilizables
- **THEN** no se reconstruyen pagos y la orden se rechaza por falta de líneas de pago válidas

### Requirement: Historial local de pedidos impresos

Tras cada impresión fiscal exitosa, el PdV DEBE (MUST) registrar en `LocalOrderHistory` (clave `l10n_ve_pos_mf_printed_orders_history` en `localStorage`) el `uuid` del pedido, su fecha, `fiscal_machine`, `mf_invoice_number`, `mf_reportz` y los métodos de pago usados con su código fiscal. El historial DEBE (MUST) deduplicar por `uid` (reemplazando la entrada previa) y limitarse a 200 entradas descartando la más antigua; los fallos de lectura o escritura del almacenamiento no DEBEN (MUST) interrumpir el flujo (`getAll` devuelve lista vacía).

#### Scenario: Reimpresión del mismo pedido

- **WHEN** un pedido ya presente en el historial se registra de nuevo
- **THEN** la entrada anterior se elimina y queda una sola entrada para ese `uid`

#### Scenario: Historial lleno

- **WHEN** el historial ya tiene 200 entradas y se agrega otra
- **THEN** se descarta la entrada más antigua

### Requirement: Conversión del descuento global a descuento por línea

Antes de validar o imprimir, `_applyGlobalDiscountBeforeValidation` DEBE (MUST) convertir las líneas del producto de descuento global (identificadas por `config.discount_product_id`) con precio negativo en un descuento porcentual por línea: infiere la tasa como el monto pendiente de descuento dividido entre el total ya descontado de las demás líneas, por cien, redondeado a 0.01 y limitado a 100 (marcando `global_clamped` cuando la tasa cruda supera 100 o cuando no hay base positiva); elimina las líneas de descuento global de la orden; resetea a 0% el descuento de todas las líneas restantes; y aplica la tasa inferida a todas las líneas con cantidad y precio no negativos. El resultado DEBE (MUST) quedar guardado en la orden como `global_discount_amount` (tasa aplicada sobre el total crudo), `global_discount_rate` y `global_clamped`. Solo actúa sobre órdenes en estado `draft`.

#### Scenario: Descuento global convertido

- **WHEN** la orden tiene líneas por 100 Bs y una línea de descuento global de -10 Bs
- **THEN** la línea de descuento se elimina, todas las líneas quedan con 10% de descuento y la orden guarda `global_discount_rate = 10`

#### Scenario: Descuento mayor al subtotal

- **WHEN** el monto de descuento global excede el total descontado de las líneas
- **THEN** la tasa se limita a 100% y `global_clamped` queda en verdadero

#### Scenario: Orden ya validada

- **WHEN** la orden no está en estado `draft`
- **THEN** no se modifica ninguna línea y se devuelve la metadata previa si existe

### Requirement: Recálculo controlado del descuento global

El override de `applyDiscount` DEBE (MUST) evitar recálculos en cascada: no hace nada si la orden no está en `draft` o si ya hay una conversión en curso (`_mf_applying_global_discount`), y solo recalcula cuando la llamada proviene de un gesto manual del cajero (`ControlButtons.applyDiscount` marca `_mf_manual_discount_trigger`) o cuando aún quedan líneas de descuento global pendientes. Con un porcentaje menor o igual a cero DEBE (MUST) resetear a 0% el descuento de todas las líneas que no son el producto de descuento y limpiar la metadata de descuento global de la orden.

#### Scenario: Re-disparo automático sin líneas pendientes

- **WHEN** el mecanismo de descuento del core vuelve a invocar `applyDiscount` sin gesto manual y ya no quedan líneas de descuento global negativas
- **THEN** la llamada se ignora y la orden no se modifica

#### Scenario: Descuento en cero

- **WHEN** el cajero aplica un descuento de 0%
- **THEN** todas las líneas quedan con 0% de descuento y la orden pierde la metadata de descuento global

### Requirement: Traducción de la orden al formato del driver

`_convertOrderForDriver(order, invoiceData)` DEBE (MUST) producir el objeto que espera el driver de `l10n_ve_mf_base`: excluye las líneas con precio negativo (acumulándolas como `global_discount_amount` solo cuando no hay conversión previa de descuento global, en cuyo caso también calcula la tasa contra la base positiva y la limita a 100 marcando `global_clamped`); emite cada línea con `product_name`, `product_code`, `price_unit` neto, `quantity`, `fiscal_code` y `discount = 0`; emite los pagos como `payment_method_code` y monto en valor absoluto; y adjunta `flag_21`, `has_cashbox`, `additional_lines` (las `info`), `invoice_affected`, la metadata de descuento global y las líneas de encabezado y pie tomadas de `receipt_header` y `receipt_footer` de la caja. Cuando ya hubo conversión previa de descuento global, el precio de la línea DEBE (MUST) ser el neto del descuento de línea, sin volver a aplicar la tasa global.

#### Scenario: Descuento ya convertido a descuento de línea

- **WHEN** la orden trae metadata de descuento global previa
- **THEN** el precio enviado es el precio neto del descuento de línea y la tasa global no se vuelve a aplicar

#### Scenario: Línea de descuento no convertida

- **WHEN** el payload llega con una línea de precio negativo y sin metadata previa
- **THEN** esa línea no se envía como ítem y su monto se acumula en `global_discount_amount` con la tasa correspondiente

### Requirement: Líneas de encabezado y pie del ticket

`_extractReceiptLines(campo)` DEBE (MUST) derivar las líneas de encabezado y pie del ticket desde `receipt_header` y `receipt_footer` de la caja, eliminando las etiquetas HTML, descartando los renglones vacíos, limitando a un máximo de 10 líneas y truncando cada línea a 127 caracteres.

#### Scenario: Encabezado con HTML y renglones vacíos

- **WHEN** `receipt_header` contiene etiquetas HTML y líneas en blanco
- **THEN** solo se envían las líneas con texto, sin etiquetas, como máximo 10 y truncadas a 127 caracteres

### Requirement: Impresión fiscal bloqueante en la validación de pago

El override de `OrderPaymentValidation.finalizeValidation` DEBE (MUST) ejecutar, antes de la sincronización del core: (1) la conversión del descuento global, cuyo fallo se registra pero no bloquea; y (2) la impresión fiscal cuando hay máquina conectada (`useFiscalMachine()`) y la orden aún no tiene `mf_invoice_number`. Si la impresión fiscal falla o lanza excepción, DEBE (MUST) devolverse `false` sin llamar a la sincronización, dejando la orden sin validar. Solo si la impresión fue exitosa (o se omitió por no haber máquina conectada) se invoca `super.finalizeValidation`.

#### Scenario: Impresión fiscal fallida

- **WHEN** el cajero valida una orden pagada y la impresión en la máquina fiscal devuelve error
- **THEN** la validación se aborta devolviendo `false`, la orden no se sincroniza y el error ya fue mostrado en un diálogo

#### Scenario: Sin máquina fiscal conectada

- **WHEN** no hay driver conectado
- **THEN** la impresión fiscal se omite y la validación continúa con el flujo estándar del core

#### Scenario: Orden ya impresa

- **WHEN** la orden ya tiene `mf_invoice_number`
- **THEN** no se vuelve a imprimir y la validación continúa

### Requirement: Selección del comando de impresión y persistencia del resultado en la orden

`pushToMF(order)` DEBE (MUST) exigir un driver conectado (devolviendo el error de máquina no conectada en caso contrario), construir el payload, rechazar cuando este no es válido, y enrutar la impresión según el tipo: `out_invoice` a `printInvoice`, `out_refund` a `printCreditNote` y `out_debit` a `printDebitNote`, devolviendo error para cualquier otro tipo. Ante una respuesta exitosa DEBE (MUST) escribir en la orden `fiscal_machine` (con `"TFHKA-LOCAL"` como último recurso), `mf_invoice_number` y `mf_reportz` (`set_data_from_fiscal_machine`). Todo error DEBE (MUST) mostrarse al cajero en un diálogo.

#### Scenario: Nota de crédito

- **WHEN** el payload resuelve el tipo `out_refund`
- **THEN** se invoca `printCreditNote` del driver y no `printInvoice`

#### Scenario: Máquina desconectada

- **WHEN** se intenta imprimir sin driver conectado
- **THEN** se muestra el diálogo indicando que la máquina fiscal no está conectada y no se envía ningún comando

#### Scenario: Impresión exitosa

- **WHEN** el driver responde con éxito
- **THEN** la orden queda con `fiscal_machine`, `mf_invoice_number` y `mf_reportz` poblados y el pedido se registra en el historial local

### Requirement: Aviso de descuento global limitado

Cuando la respuesta del driver trae `global_clamped`, el PdV DEBE (MUST) mostrar un diálogo de aviso indicando el monto del descuento global y la tasa máxima realmente aplicada en el comprobante, sin abortar la impresión ya realizada.

#### Scenario: Descuento que excede el subtotal

- **WHEN** la impresión termina con `global_clamped` verdadero
- **THEN** se muestra el aviso con el monto y el porcentaje aplicado, y la orden se considera impresa

### Requirement: Omisión del PDF de la factura del pedido

Cuando la caja tiene `mf_skip_invoice_pdf` activo, `shouldDownloadInvoice()` DEBE (MUST) devolver `false` y `_generate_pos_order_invoice()` DEBE (MUST) generar la factura con el contexto `generate_pdf=False`, de modo que la validación fiscal no dependa del renderizador de PDF.

#### Scenario: Caja configurada para omitir el PDF

- **WHEN** la caja tiene `mf_skip_invoice_pdf = True` y se valida un pedido a facturar
- **THEN** la factura se crea sin generar ni descargar el PDF

#### Scenario: Caja sin la opción activa

- **WHEN** `mf_skip_invoice_pdf` está desactivado
- **THEN** se conserva el comportamiento del core para la descarga y generación del PDF

### Requirement: Validación contable en seco sin persistencia

`pos.order.validate_order_dry_run(orders)` DEBE (MUST) ejecutar `sync_from_ui` (con `generate_pdf=False`) dentro de un `SAVEPOINT` y hacer `ROLLBACK` SIEMPRE, tanto en éxito como en error, propagando la excepción original cuando la validación contable falla y devolviendo `True` cuando completa. Ningún dato escrito durante el ensayo DEBE (MUST) quedar persistido.

#### Scenario: Validación contable fallida

- **WHEN** `sync_from_ui` lanza un error de contabilidad durante el ensayo
- **THEN** se revierte todo lo escrito y la excepción se propaga al llamador

#### Scenario: Ensayo exitoso

- **WHEN** el ensayo completa sin errores
- **THEN** devuelve `True` y ninguno de los registros creados durante el ensayo queda en la base

### Requirement: Botón de conexión de la máquina fiscal en el PdV

El PdV DEBE (MUST) mostrar el botón `FiscalPrinterButton` en el área de botones de estado de la barra superior únicamente cuando la caja tiene `access_button_mf`. Al montarse DEBE (MUST) instanciar el `TfhkaDriver` de `l10n_ve_mf_base`, exponerlo en `window.fiscalPrinter` e intentar la conexión silenciosa (sin prompt); si el navegador no soporta Web Serial el estado pasa a `error`. Al hacer click estando desconectado DEBE (MUST) solicitar el permiso de puerto (`requestPermission: true`) y, tras conectar, verificar con `getStatus()` que la impresora responde — si no responde el estado queda en `error`; al hacer click estando conectado DEBE (MUST) desconectar. Los estados expuestos son `disconnected`, `connecting`, `connected` y `error`.

#### Scenario: Reconexión silenciosa al abrir el PdV

- **WHEN** se abre el PdV con `access_button_mf` activo y existe un puerto previamente autorizado
- **THEN** el botón se monta, conecta sin prompt y queda en estado `connected` con el driver en `window.fiscalPrinter`

#### Scenario: Primera autorización de puerto

- **WHEN** el cajero hace click con la máquina desconectada y sin puerto autorizado
- **THEN** se dispara el prompt de selección de puerto de Web Serial

#### Scenario: Impresora que no responde

- **WHEN** el puerto se abre pero `getStatus()` no devuelve estado
- **THEN** el botón queda en estado `error`

#### Scenario: Navegador sin Web Serial

- **WHEN** el navegador no expone `navigator.serial`
- **THEN** el botón queda en estado `error` y no se instancia ninguna conexión

### Requirement: Apertura de la gaveta a través de la máquina fiscal

`openCashbox` DEBE (MUST) abrir la gaveta con el comando de la impresora (`openDrawer()`) cuando hay driver conectado y la caja tiene `has_cashbox`, sin delegar al mecanismo del core; si la llamada al driver lanza una excepción, o si no hay driver conectado o la caja no tiene gaveta configurada, DEBE (MUST) delegarse al comportamiento del core.

#### Scenario: Gaveta conectada a la impresora fiscal

- **WHEN** se solicita abrir la gaveta con la máquina conectada y `has_cashbox` activo
- **THEN** se envía el comando de apertura al driver y no se usa el mecanismo del core

#### Scenario: Sin máquina fiscal

- **WHEN** no hay driver conectado
- **THEN** la apertura de gaveta la maneja el core

### Requirement: Filtro de pedidos pendientes por facturar

La pantalla de pedidos DEBE (MUST) ofrecer el filtro "Pendientes por facturar" (`UNFISCALIZED`) que agrega la condición `mf_invoice_number = False` al dominio de pedidos sincronizados y lista los pedidos finalizados sin número fiscal, ordenados por fecha descendente y paginados. Al seleccionar el filtro o buscar dentro de él DEBEN (MUST) recargarse los pedidos desde el servidor.

#### Scenario: Selección del filtro

- **WHEN** el cajero selecciona el filtro "Pendientes por facturar"
- **THEN** los pedidos sincronizados se consultan con `mf_invoice_number = False` y se listan solo los finalizados sin número fiscal

#### Scenario: Búsqueda dentro del filtro

- **WHEN** el cajero escribe un término de búsqueda con el filtro `UNFISCALIZED` activo
- **THEN** se reinicia el desplazamiento por dominio y se vuelven a consultar los pedidos sincronizados

### Requirement: Impresión de un pedido pendiente

El botón "Imprimir pedido pendiente" DEBE (MUST) mostrarse solo para el pedido sincronizado seleccionado que NO tiene `mf_invoice_number`, exigir un driver conectado y reutilizar exactamente el mismo flujo de la validación (`get_data_invoice` + `_convertOrderForDriver` + el comando según tipo de documento). Tras una impresión exitosa DEBE (MUST) actualizar el objeto local, persistir los datos fiscales con `pos.order.write_mf_invoice_data`, navegar a la pantalla de recibo del pedido y refrescar en segundo plano la lista de pendientes recargando el pedido desde el servidor. Cualquier error DEBE (MUST) mostrarse en un diálogo sin persistir nada.

#### Scenario: Pedido pendiente impreso

- **WHEN** el cajero imprime un pedido sincronizado sin número fiscal y el driver responde con éxito
- **THEN** se llama a `write_mf_invoice_data` con número, serial y Reporte Z, se navega al recibo y el pedido deja de aparecer en la lista de pendientes

#### Scenario: Pedido ya facturado

- **WHEN** el pedido seleccionado ya tiene `mf_invoice_number`
- **THEN** el botón no se muestra y la acción no se ejecuta

#### Scenario: Error de impresión

- **WHEN** el driver devuelve error al imprimir el pedido pendiente
- **THEN** se muestra el diálogo con el error y no se persiste ningún dato fiscal

### Requirement: Persistencia y propagación de los datos fiscales del pedido

`pos.order` DEBE (MUST) tener los campos `mf_invoice_number`, `fiscal_machine` y `mf_reportz` (Char, `copy=False`, `readonly=True`) y exponerlos al PdV vía `_load_pos_data_fields`. `write_mf_invoice_data(mf_invoice_number, fiscal_machine, mf_reportz)` DEBE (MUST) escribirlos con `sudo()` (por ser readonly a nivel de modelo), validar la compañía del registro y propagar los mismos datos al `account.move` asociado como `mf_invoice_number`, `mf_serial` y `mf_reportz`, devolviendo `success` y `account_move_updated`; cuando el pedido no tiene factura contable la propagación se omite y queda registrada en el log.

#### Scenario: Pedido con factura contable

- **WHEN** se llama a `write_mf_invoice_data` en un pedido que ya generó `account.move`
- **THEN** el pedido y la factura quedan con los datos fiscales y `account_move_updated` es verdadero

#### Scenario: Pedido sin factura contable

- **WHEN** el pedido no tiene `account_move`
- **THEN** solo se escriben los campos del pedido y `account_move_updated` es falso

### Requirement: Datos fiscales y fecha en la factura del pedido

`_prepare_invoice_vals` DEBE (MUST) trasladar a la factura del pedido la caja de origen (`cashbox_id`) y los datos fiscales (`mf_serial` desde `fiscal_machine`, `mf_invoice_number` y `mf_reportz`), y DEBE (MUST) fijar `invoice_date` como la fecha del pedido (`date_order`) convertida a la zona horaria del usuario del pedido, del usuario actual o `America/Caracas` como respaldo; si la sesión ya está cerrada se usa la fecha actual.

#### Scenario: Pedido de una sesión abierta

- **WHEN** se factura un pedido de una sesión abierta con `date_order` de ayer en horario de Caracas
- **THEN** `invoice_date` es la fecha local del pedido y no la del momento de la facturación

#### Scenario: Datos fiscales heredados

- **WHEN** el pedido ya tiene número fiscal y serial
- **THEN** la factura se crea con `mf_invoice_number`, `mf_serial` y `mf_reportz` iguales a los del pedido

### Requirement: Reimpresión del documento fiscal desde la pantalla de pedidos

El botón "Reimprimir Documento Fiscal" DEBE (MUST) mostrarse solo para el pedido sincronizado seleccionado que YA tiene `mf_invoice_number`, exigir un driver conectado y llamar a `TfhkaDriver.reprintDocument` con el número fiscal del pedido y el tipo derivado del signo del total (`out_invoice` cuando el total es mayor o igual a cero, `out_refund` cuando es negativo), informando el resultado en un diálogo.

#### Scenario: Reimpresión de una devolución

- **WHEN** el pedido seleccionado tiene número fiscal y total negativo
- **THEN** se reimprime con el tipo `out_refund`

#### Scenario: Sin máquina conectada

- **WHEN** no hay driver conectado
- **THEN** se avisa que la máquina fiscal no está conectada y no se envía el comando de reimpresión

### Requirement: Cierre de sesión bloqueado por pedidos sin facturar

El botón nativo de cierre de caja DEBE (MUST) reemplazarse por "Cerrar sesion e imprimir Z", que antes de cualquier otra acción consulta los pedidos de la sesión con `mf_invoice_number = False` y estado distinto de `cancel`. Si existen, DEBE (MUST) mostrar un diálogo con la cantidad y hasta 10 nombres de pedidos (indicando cuántos quedan por mostrar), cerrar el popup de cierre y navegar a la pantalla de pedidos con el filtro `UNFISCALIZED` preseleccionado, sin imprimir el Reporte Z ni cerrar la sesión.

#### Scenario: Sesión con pedidos sin facturar

- **WHEN** el cajero pulsa "Cerrar sesion e imprimir Z" y quedan 12 pedidos sin número fiscal
- **THEN** se listan 10 nombres con la nota de que hay 2 más, el popup se cierra y el PdV navega a la lista filtrada por pendientes por facturar

#### Scenario: Sesión sin pendientes

- **WHEN** todos los pedidos de la sesión tienen número fiscal
- **THEN** el flujo continúa con la impresión del Reporte Z

### Requirement: Reporte Z obligatorio y sincronización con Odoo

El Reporte Z desde el popup de cierre DEBE (MUST) exigir un driver conectado y una confirmación explícita del cajero (advirtiendo que la acción es irreversible), enviar `printReportZ()` y luego leer el S1: solo si la lectura es exitosa y trae `registeredMachineNumber` y un `dailyClosureCounter` entero DEBE (MUST) sincronizar Odoo llamando a `account.move.report_z` (con el serial de la caja) y a `pos.session.set_report_z`. Si el Z se imprimió pero el S1 no se pudo leer, DEBE (MUST) mostrarse una advertencia y NO continuar con el cierre de la sesión. Solo cuando el Z se imprimió y sincronizó se invoca el flujo nativo de cierre (`confirm()`), preservando la validación de diferencias de caja.

#### Scenario: Cierre completo

- **WHEN** el cajero confirma el Reporte Z, la impresión y la lectura del S1 son exitosas
- **THEN** se sincronizan `account.move.report_z` y `pos.session.set_report_z` y luego se ejecuta el cierre nativo de la sesión

#### Scenario: Confirmación rechazada

- **WHEN** el cajero cancela la confirmación del Reporte Z
- **THEN** no se envía ningún comando y la sesión no se cierra

#### Scenario: S1 ilegible tras el Z

- **WHEN** el Reporte Z se imprime pero el S1 no devuelve serial o contador válidos
- **THEN** se advierte que Odoo no quedó sincronizado y la sesión no se cierra

### Requirement: Reporte X desde el popup de cierre

El popup de cierre DEBE (MUST) ofrecer un botón de Reporte X que exija driver conectado y envíe `printReportX()` SIN confirmación ni cierre del día fiscal, informando el error en un diálogo cuando la impresión falla. Mientras hay un reporte en curso los botones del popup quedan deshabilitados.

#### Scenario: Reporte X impreso

- **WHEN** el cajero pulsa "Reporte X" con la máquina conectada
- **THEN** se envía `printReportX()` directamente, sin diálogo de confirmación, y la sesión no se cierra

### Requirement: Cierre nativo restringido por grupo

`res.users._load_pos_data_read` DEBE (MUST) exponer al PdV la clave `_can_close_session_native` según la pertenencia del usuario al grupo `l10n_ve_pos_mf.group_pos_close_native`. Solo para esos usuarios el popup de cierre DEBE (MUST) mostrar el botón adicional de cierre nativo, que cierra la sesión sin imprimir Reporte Z ni validar los pedidos sin facturar.

#### Scenario: Usuario sin el grupo

- **WHEN** un cajero sin `group_pos_close_native` abre el popup de cierre
- **THEN** solo dispone de "Cerrar sesion e imprimir Z" y del Reporte X

#### Scenario: Usuario con el grupo

- **WHEN** un usuario con `group_pos_close_native` abre el popup de cierre
- **THEN** dispone además del botón de cierre nativo que omite el Reporte Z y la validación de pendientes

### Requirement: Sincronización del Reporte Z con los pedidos del PdV

El override de `account.move.report_z(serial, response)` DEBE (MUST) encadenar la implementación del módulo de facturación fiscal cuando existe (`super`) y, si no existe, aplicar la réplica local `_report_z_base` — que lanza `ValidationError` cuando `response.valid` es falso y asigna `mf_reportz = contador + 1` a las facturas del serial sin Z, usando `_dailyClosureCounter` o, en su ausencia, el último `mf_reportz` registrado para ese serial (0 si no hay historial). En ambos casos DEBE (MUST) además asignar `mf_reportz = resultado + 1` a todos los `pos.order` cuyo `fiscal_machine` coincide con `_registeredMachineNumber` de la respuesta y aún no tienen Z.

#### Scenario: POS con módulo de facturación fiscal instalado

- **WHEN** se llama a `report_z` con `l10n_ve_account_mf` instalado
- **THEN** primero se ejecuta la lógica de facturación y luego se completan los pedidos PdV pendientes de ese serial

#### Scenario: POS sin módulo de facturación fiscal

- **WHEN** solo está instalado `l10n_ve_pos_mf` y `response.valid` es falso
- **THEN** se lanza `ValidationError` y no se asigna Reporte Z a ningún registro

### Requirement: Reporte Z de la sesión del PdV

`pos.session` DEBE (MUST) tener el campo `report_z` y el campo relacionado `serial_machine` (de la caja), cargados en el PdV, y `set_report_z(values)` DEBE (MUST) escribir en la sesión `report_z = _dailyClosureCounter + 1` tomado de la respuesta del S1.

#### Scenario: Sincronización del Z en la sesión

- **WHEN** se llama a `set_report_z` con `_dailyClosureCounter = 41`
- **THEN** la sesión queda con `report_z = 42`

### Requirement: Recuperación de los datos fiscales de un pedido por identificador

`pos.order.get_order_by_uid(uid)` DEBE (MUST) buscar el pedido primero por `pos_reference` (coincidencia parcial) y, si no hay resultado, por `uuid` exacto, devolviendo lista vacía cuando no encuentra nada. Para los pedidos encontrados DEBE (MUST) devolver `pos_reference`, `date_order`, `fiscal_machine`, `mf_invoice_number` y `mf_reportz`, más `payment_lines` con el código fiscal del método (`code_fiscal_printer`), su nombre y el monto, omitiendo los pagos sin método.

#### Scenario: Búsqueda por uuid

- **WHEN** se consulta un `uid` que no coincide con ningún `pos_reference` pero sí con un `uuid`
- **THEN** se devuelve ese pedido con sus datos fiscales y sus líneas de pago con código fiscal

#### Scenario: Pedido inexistente

- **WHEN** el `uid` no coincide con ningún pedido
- **THEN** se devuelve una lista vacía

### Requirement: El comprobante del PdV lo emite la máquina fiscal

La interfaz del PdV DEBE (MUST) suprimir la emisión de comprobantes propios cuando se factura con máquina fiscal: la pantalla de recibo elimina el botón de impresión completa y el contenedor del recibo del core, y la pantalla de pedidos elimina el botón de facturación manual. En su lugar, para el pedido con `mf_invoice_number` la pantalla de recibo DEBE (MUST) mostrar el bloque fiscal con el título "Nota de Crédito Impresa" cuando el total es negativo o "Factura Fiscal Impresa" en caso contrario, junto al número fiscal, el serial de la máquina y el Reporte Z cuando existen. La lista de pedidos DEBE (MUST) incluir una columna con el número fiscal (`mf_invoice_number`) de cada pedido.

#### Scenario: Recibo de una nota de crédito

- **WHEN** el pedido impreso tiene `mf_invoice_number` y total negativo
- **THEN** la pantalla de recibo muestra "Nota de Crédito Impresa" con el número fiscal, el serial y el Reporte Z, sin el recibo del core

#### Scenario: Pedido sin número fiscal

- **WHEN** el pedido no tiene `mf_invoice_number`
- **THEN** no se muestra el bloque fiscal y su celda de número fiscal en la lista queda vacía

### Requirement: Clasificación del documento para el libro de ventas

`account.move.sales_book_type` DEBE (MUST) calcularse como `02-REG` para notas de crédito y de débito publicadas (`out_refund`, `out_debit`), `03-ANU` para facturas, notas de crédito y notas de débito canceladas, y `01-REG` en cualquier otro caso.

#### Scenario: Nota de crédito publicada

- **WHEN** el documento es `out_refund` en estado `posted`
- **THEN** `sales_book_type` es `02-REG`

#### Scenario: Factura anulada

- **WHEN** una factura de cliente está en estado `cancel`
- **THEN** `sales_book_type` es `03-ANU`

### Requirement: Libro de Ventas agrupado por Reporte Z

El wizard `wizard.sales.book` DEBE (MUST) construir el Libro de Ventas únicamente con los documentos de venta que tienen datos fiscales completos: `invoice_date` dentro del rango, estado distinto de `draft`, `move_type` en `out_invoice`/`out_refund`/`out_debit`, `mf_serial` presente y `mf_reportz` presente; ordenados por `mf_invoice_number` y agrupados por `mf_reportz`. Las facturas consecutivas de contribuyentes ordinarios DEBEN (MUST) consolidarse en una línea de resumen diario (`RESUMEN` / "Resumen Diario de Ventas") con el rango "Desde ... Hasta ..." de números fiscales, cortando el resumen al cambiar la fecha del documento, al encontrar un contribuyente con `prefix_vat` `J` o `taxpayer` especial, al cambiar el tipo de documento o al llegar al último documento del grupo. Las bases y débitos por alícuota (16%, 8%, 31%) y el total exento DEBEN (MUST) tomarse de `amount_by_group_base` cuando la moneda de la compañía es VEF y de `foreign_amount_by_group_base` en caso contrario, y los montos de las notas de crédito DEBEN (MUST) invertirse de signo. Las retenciones de IVA del rango (`account.retention` por `date_accounting`) DEBEN (MUST) reflejarse con su fecha, número y monto retenido, y las facturas con retención que no entraron en el dominio DEBEN (MUST) agregarse al final. Las líneas DEBEN (MUST) quedar ordenadas por número de Reporte Z.

#### Scenario: Facturas de contribuyentes ordinarios del mismo día

- **WHEN** un Reporte Z agrupa varias facturas consecutivas de contribuyentes ordinarios de la misma fecha
- **THEN** se emite una sola línea "Resumen Diario de Ventas" con el rango de números fiscales y los totales acumulados

#### Scenario: Factura a contribuyente especial

- **WHEN** dentro del grupo aparece un documento cuyo cliente es contribuyente especial o tiene `prefix_vat` `J`
- **THEN** el resumen acumulado se cierra y ese documento se detalla en su propia línea

#### Scenario: Documento sin Reporte Z

- **WHEN** una factura tiene `mf_serial` pero no `mf_reportz`
- **THEN** no aparece en el Libro de Ventas

#### Scenario: Nota de crédito

- **WHEN** el documento es `out_refund`
- **THEN** sus totales, bases, impuestos y retención se registran con signo invertido

### Requirement: Descarga del Libro de Ventas en XLSX

El wizard DEBE (MUST) ofrecer la descarga del Libro de Ventas como archivo XLSX mediante la ruta autenticada `/web/binary/download_sales_book` con `date_from` y `date_to`, devolviendo el archivo como adjunto `Libro_de_venta.xlsx`. Las fechas mostradas DEBEN (MUST) formatearse como `DD/MM/YYYY` y el encabezado del reporte DEBE (MUST) incluir el nombre y el RIF de la compañía junto al rango de fechas. Por defecto el rango cubre el mes en curso (del primer al último día).

#### Scenario: Generación del archivo

- **WHEN** el usuario pulsa "Generar Informe" con un rango de fechas
- **THEN** el navegador descarga `Libro_de_venta.xlsx` con el encabezado de la compañía, el rango en formato `DD/MM/YYYY` y las columnas de totales sumadas

### Requirement: Fiscalizador del PdV

El PdV DEBE (MUST) ofrecer, desde el widget de depuración, el Fiscalizador: un diálogo que intercepta `sendCommand` del driver para registrar cada trama enviada y cada respuesta recibida con su duración (limitando la bitácora a 100 entradas y descartando las más antiguas, sin volver a interceptar si ya lo está), permite enviar comandos crudos con ayuda contextual según el error, leer y refrescar el estado (manual o automático cada 2 segundos) con el parser de `l10n_ve_mf_base`, consultar el diagnóstico S3 de tasas y flags, programar flags con el comando `PJ<número><valor>` y exportar la bitácora a un archivo de texto. Si la impresora no está conectada, cada acción DEBE (MUST) reportarlo en lugar de enviar comandos.

#### Scenario: Traza de un comando

- **WHEN** se envía un comando con el Fiscalizador abierto
- **THEN** la bitácora registra el comando enviado y la respuesta recibida con su duración en milisegundos

#### Scenario: Impresora desconectada

- **WHEN** se abre el Fiscalizador sin impresora conectada
- **THEN** la bitácora registra el aviso de impresora no conectada y no se envía ningún comando

#### Scenario: Diagnóstico S3 no soportado

- **WHEN** el driver activo no expone `readS3Data`
- **THEN** se informa que el driver no soporta la lectura S3 y no se muestran datos

### Requirement: Sincronización de dispositivos tolerante a fechas inválidas

La construcción del dominio de sincronización entre dispositivos (`DevicesSynchronisation.constructOrdersDomain`) DEBE (MUST) omitir, registrando la advertencia, todo registro cuyo `write_date` sea ausente o no sea una fecha válida, y capturar los errores de procesamiento por registro, de modo que un registro con fecha corrupta no interrumpa la sincronización del resto.

#### Scenario: Registro con write_date inválido

- **WHEN** un registro sincronizado llega sin `write_date` utilizable
- **THEN** se omite con una advertencia y el dominio se construye con los registros restantes
