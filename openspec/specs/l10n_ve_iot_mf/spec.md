# l10n_ve_iot_mf

## Purpose

Integra impresoras fiscales The Factory HKA y PnP Desarrollos con Facturación por la vía **IoT Box** (DLLs y drivers seriales ejecutándose en la caja IoT), que es la ruta previa a la integración Web Serial de `l10n_ve_mf_base` / `l10n_ve_account_mf`. Extiende `iot.box`, `iot.device`, `account.move`, `account.journal`, `account.tax`, `res.company` y el asistente `wizard.accounting.reports`; agrega el modelo `iot.port`, dos endpoints HTTP para que la caja IoT descubra qué puertos usar, y los drivers/SDK que corren del lado de la caja. Depende de `iot`, `account`, `web`, `l10n_ve_invoice` (aporta `correlative`, `is_debit_journal`, `invoice_date_display`, `foreign_price`), `l10n_ve_tax_payer` (aporta `taxpayer_type`, `prefix_vat`) y `l10n_ve_stock_account`.

## Requirements

### Requirement: Reasignación de puertos fiscales al renombrar el módulo

El `pre_init_hook` DEBE (MUST) reasignar en `ir_model_data` al módulo `l10n_ve_iot_mf` los xml_ids con prefijo `iot_port_com_` que pertenecían al módulo anterior `binaural_iot_mf`, evitando duplicar la data de puertos en bases que migran.

#### Scenario: Instalación sobre una base que venía del módulo anterior

- **WHEN** se instala `l10n_ve_iot_mf` en una base donde los puertos fueron cargados por `binaural_iot_mf`
- **THEN** los registros de `iot.port` quedan asociados al módulo nuevo y no se duplican

### Requirement: Puertos fiscales y lista negra por caja IoT

El modelo `iot.box` DEBE (MUST) exponer el indicador `has_fiscal_machine` con los puertos habilitados en `fiscal_port_ids`, y el indicador `blacklist` con los puertos vedados en `blacklist_port_ids`, ambos hacia el modelo `iot.port` (definido en este módulo, con un único campo `name`).

Los cuatro campos Muchos-a-muchos (`iot.box.fiscal_port_ids`, `iot.box.blacklist_port_ids`, `iot.port.iot_box_ids`, `iot.port.iot_box_blacklist_ids`) reciben su segundo argumento posicional como **nombre de la tabla de relación**, no como campo inverso, así que cada uno DEBE (MUST) entenderse como una relación independiente: lo que se asigna desde la caja IoT no se refleja al abrir el puerto desde `iot.port`.

#### Scenario: Caja con máquina fiscal declarada

- **WHEN** un administrador marca `has_fiscal_machine` en una caja IoT y le asigna puertos
- **THEN** esos puertos quedan registrados en `fiscal_port_ids` de esa caja

#### Scenario: Lectura desde el puerto

- **WHEN** se abre uno de esos `iot.port` y se consulta `iot_box_ids`
- **THEN** la caja no aparece, porque ese campo usa otra tabla de relación

### Requirement: Publicación de los puertos fiscales a las cajas IoT

Los endpoints HTTP `/iot_fiscal/ports` y `/iot_blacklist/ports` DEBEN (MUST) devolver, como texto serializado con `json.dumps`, un mapa del `identifier` de cada caja IoT a la lista de nombres de sus puertos: el primero para las cajas con `has_fiscal_machine` activo y el segundo para las cajas con `blacklist` activo. Ambas rutas son `type="http"`, `methods=["GET"]`, `csrf=False` y `auth="public"`, y leen con `sudo()`: DEBEN (MUST) responder sin autenticación ni control de acceso, exponiendo los identificadores de todas las cajas y sus puertos a cualquiera que alcance la instancia.

#### Scenario: Consulta de puertos fiscales

- **WHEN** una caja IoT consulta `/iot_fiscal/ports`
- **THEN** recibe el mapa con el identificador de cada caja con máquina fiscal y los nombres de sus puertos habilitados

#### Scenario: Consulta anónima

- **WHEN** un cliente sin sesión ni credenciales hace GET a `/iot_fiscal/ports`
- **THEN** recibe la misma respuesta completa, sin desafío de autenticación

### Requirement: Identificación del fabricante por el nombre del dispositivo

El campo calculado `manufacturer_type` de `iot.device` DEBE (MUST) valer `HKA` cuando el nombre del dispositivo contiene "HKA", `PnP` cuando contiene "PnP", y quedar sin valor cuando el nombre no contiene ninguna de las dos cadenas. La comparación es sensible a mayúsculas y se evalúa sobre `name` sin guarda: el cómputo no declara `@api.depends` ni almacena el resultado, y con `name` vacío (`False`) DEBE (MUST) entenderse que falla al evaluar la pertenencia en lugar de devolver "sin valor".

#### Scenario: Dispositivo TFHKA

- **WHEN** el nombre del dispositivo contiene "HKA"
- **THEN** `manufacturer_type` es `HKA`

#### Scenario: Dispositivo sin nombre

- **WHEN** se calcula `manufacturer_type` de un dispositivo cuyo `name` está vacío
- **THEN** el cómputo falla en la evaluación de la cadena y no devuelve un valor vacío

### Requirement: Registro del serial de la máquina fiscal en el dispositivo

El método `set_serial_machine` DEBE (MUST) guardar en `serial_machine` el número de máquina registrado que devuelve la impresora (`res["data"]["_registeredMachineNumber"]`, de la acción `get_last_invoice_number` y solo cuando el frontend recibió `valid`) y renombrar el dispositivo al formato `<serial> - Fiscal Printer HKA`, con ese sufijo fijo incluso si el fabricante es PnP.

#### Scenario: Alta del dispositivo tras consultar la máquina

- **WHEN** se ejecuta `set_serial_machine` con la respuesta de la impresora
- **THEN** el dispositivo queda con ese serial y su nombre pasa a incluirlo

### Requirement: Configuración de banderas y modo del dispositivo fiscal

El dispositivo DEBE (MUST) exponer la configuración que se envía a la impresora vía `configure_device`: `flag_21` (valores `30`, `00`, `01`, `02`, por defecto `00`), `flag_24` (`00` u `01`, por defecto `00`) y `show_version`, que se transmite como `77` cuando está activo y `00` cuando no.

#### Scenario: Envío de configuración con versión visible

- **WHEN** se invoca `configure_device` en un dispositivo con `show_version` activo
- **THEN** el valor enviado para la versión es `77`

### Requirement: Validación del método de pago del dispositivo

El método `get_data_to_payment_method` DEBE (MUST) rechazar la operación cuando el nombre del método de pago (`payment_method_name`) está vacío o cuando no se ha seleccionado un identificador de método de pago (`payment_methods`), lanzando un error de validación en cada caso.

#### Scenario: Método de pago sin nombre

- **WHEN** se solicitan los datos del método de pago y `payment_method_name` está vacío
- **THEN** se lanza un error indicando que el nombre del método de pago está vacío

### Requirement: Validación de rangos de reimpresión

El método `get_range_reprint` DEBE (MUST) exigir ambos extremos del rango según el tipo elegido (`reprint_type` en `number` exige los campos de número, en `date` los de fecha) y rechazar los rangos invertidos (extremo final menor que el inicial). Para el tipo `date` los extremos se transmiten en formato `ddmmyy`, y el modo se toma de `reprint_type_number` o `reprint_type_date` según corresponda.

El campo `reprint_type` no tiene valor por defecto y la construcción del payload solo distingue `number`: cualquier otro valor, incluido `reprint_type` sin seleccionar, DEBE (MUST) resolverse por la rama de fechas, con lo que un `reprint_type` vacío no dispara ninguna de las dos validaciones y devuelve el rango de fechas (que sí tiene por defecto la fecha de hoy) con el modo de `reprint_type_date`. La comparación del rango numérico convierte ambos extremos con `int()`, por lo que un número no íntegro aborta con un error de conversión y no con un error de validación.

#### Scenario: Rango de números invertido

- **WHEN** se solicita una reimpresión por número con el número final menor que el inicial
- **THEN** se lanza un error indicando que el rango final es mayor que el inicial y no se envía nada a la impresora

#### Scenario: Reimpresión por fechas

- **WHEN** se solicita una reimpresión por fechas con un rango válido
- **THEN** los extremos se envían con formato `ddmmyy` junto al modo del tipo de documento

#### Scenario: Tipo de reimpresión sin seleccionar

- **WHEN** se invoca `get_range_reprint` con `reprint_type` vacío
- **THEN** no se valida ningún extremo y se devuelve el rango de fechas por defecto con el modo de `reprint_type_date`

### Requirement: Validación del rango de resumen

El método `get_range_resume` DEBE (MUST) exigir ambos extremos del rango (`resume_range_from` y `resume_range_to`) y rechazar el rango invertido, transmitiendo las fechas en formato `ddmmyy`.

#### Scenario: Rango de resumen invertido

- **WHEN** la fecha final del resumen es anterior a la inicial
- **THEN** se lanza un error de validación

### Requirement: Tipo de impresión de factura por compañía

La compañía DEBE (MUST) exponer el campo `invoice_print_type` con los valores `free` (Forma Libre, por defecto) y `fiscal` (Máquina Fiscal), configurable desde los ajustes generales como campo relacionado editable, y el documento contable lo refleja en su campo almacenado `print_type`.

#### Scenario: Compañía configurada en máquina fiscal

- **WHEN** un administrador selecciona "Máquina Fiscal" como tipo de impresión y guarda
- **THEN** las facturas de esa compañía quedan con `print_type` en `fiscal`

### Requirement: Máquina fiscal asignada al documento

El documento contable DEBE (MUST) exponer la máquina fiscal en `iot_mf` (limitada por dominio a dispositivos con `serial_machine` establecido), su caja IoT en el campo relacionado `iot_box`, y los datos de la impresión fiscal en `mf_serial`, `mf_invoice_number` y `mf_reportz`. Los cinco campos son `copy=False`, pero solo los tres campos de datos fiscales (`mf_serial`, `mf_invoice_number`, `mf_reportz`) llevan `tracking=True`: `iot_mf` e `iot_box` no se registran en el chatter.

El valor por defecto de `iot_mf` es el primer `iot.device` de tipo `fiscal_data_module`, buscado **sin** el filtro de `serial_machine`, por lo que DEBE (MUST) poder preseleccionar un dispositivo que el dominio del campo no admite.

#### Scenario: Documento nuevo en una instalación con una sola máquina

- **WHEN** se crea un documento contable y existe un dispositivo de tipo `fiscal_data_module` con serial
- **THEN** ese dispositivo queda preseleccionado como máquina fiscal del documento

#### Scenario: Dispositivo fiscal sin serial registrado

- **WHEN** el único dispositivo `fiscal_data_module` aún no tiene `serial_machine`
- **THEN** queda igualmente preseleccionado en `iot_mf` aunque quede fuera del dominio del campo

#### Scenario: Duplicación de un documento impreso

- **WHEN** se duplica un documento que ya tiene número fiscal y serial
- **THEN** la copia no arrastra `mf_invoice_number`, `mf_serial` ni la máquina asignada

### Requirement: Validaciones previas a imprimir una factura fiscal

El método `check_print_out_invoice` DEBE (MUST) rechazar la impresión cuando el documento ya tiene `mf_invoice_number` (ya fue impreso), cuando no tiene máquina fiscal asignada, cuando está en estado `draft` o `cancel`, cuando su fecha de documento (`invoice_date_display`) no es la fecha de hoy, o cuando está marcado como factura a crédito (`is_credit`) y tiene pagos aplicados (`amount_residual` distinto de `amount_total`).

#### Scenario: Factura ya impresa

- **WHEN** se intenta imprimir una factura que ya tiene número fiscal
- **THEN** se lanza un error indicando que la factura ya fue impresa

#### Scenario: Factura de otra fecha

- **WHEN** se intenta imprimir una factura cuya fecha de documento no es la del día
- **THEN** se lanza un error y no se envía nada a la impresora

### Requirement: Construcción de los datos de impresión fiscal

Los datos enviados a la impresora DEBEN (MUST) incluir la bandera `flag_21` y el identificador del dispositivo, la IP de la caja IoT, el nombre de la compañía, los datos del cliente (nombre normalizado, RIF como `<prefix_vat>-<vat>`, dirección y teléfono), las líneas y los pagos. Cada línea lleva el código fiscal del primer impuesto de la línea (`tax_ids[0].fiscal_code`, o `0` sin impuestos), la cantidad y la descripción normalizada con el formato `[<código interno>] <nombre>` cuando hay producto. Si la moneda de la compañía no es VEF, el precio unitario se toma de `foreign_price` en lugar de `price_unit`.

#### Scenario: Línea sin impuestos

- **WHEN** una línea de la factura no tiene impuestos
- **THEN** el código fiscal enviado para esa línea es `0`

#### Scenario: Compañía en moneda distinta de VEF

- **WHEN** la moneda de la compañía no es VEF
- **THEN** el precio unitario enviado a la impresora es el de `foreign_price`

### Requirement: Normalización de descripciones para la impresora fiscal

El método `_normalize_product_name` DEBE (MUST) descomponer los acentos y eliminar los diacríticos, sustituir por espacios todo carácter que no sea alfanumérico ni espacio, colapsar los espacios repetidos y recortar los extremos, devolviendo cadena vacía cuando no hay nombre.

#### Scenario: Nombre con acentos y signos

- **WHEN** se normaliza un nombre con tildes y signos de puntuación
- **THEN** el resultado no contiene diacríticos ni signos, y no tiene espacios repetidos

### Requirement: Conversión de pagos a la moneda fiscal

Los pagos enviados a la impresora se toman del widget de pagos (`invoice_payments_widget`) y DEBEN (MUST) llevar el código de método de pago (`account.journal.payment_method`, Char de dos caracteres, por defecto `01`) del diario que se localiza buscando un `account.journal` cuyo **nombre** coincida con el `journal_name` que trae el widget; si ninguna coincide, el recordset vacío hace que se use `01`. El monto se multiplica por `foreign_inverse_rate` cuando la moneda del pago no es VEF, resolviendo `base.VEF` con `raise_if_not_found=False` (si esa moneda no existe en la base, la comparación falla siempre y todos los pagos se convierten). Los montos se envían con su signo original, sin valor absoluto, también en notas de crédito. Un documento sin pagos aplicados se envía con una única línea de pago de monto `0` y método `01`.

#### Scenario: Pago en moneda extranjera

- **WHEN** el documento tiene un pago cuya moneda no es VEF
- **THEN** el monto enviado es el del pago multiplicado por la tasa inversa alterna del documento

#### Scenario: Documento sin pagos

- **WHEN** el documento no tiene pagos conciliados
- **THEN** se envía una sola línea de pago con monto `0` y método `01`

### Requirement: Registro del resultado de la impresión fiscal

Tras imprimir, los métodos `print_out_invoice`, `print_out_refund` y `print_debit_note` DEBEN (MUST) guardar en el documento el número de secuencia devuelto por la impresora en `mf_invoice_number` y el serial de la máquina en `mf_serial`.

#### Scenario: Impresión exitosa

- **WHEN** la impresora devuelve secuencia y serial
- **THEN** el documento queda con ese número fiscal y serial registrados

### Requirement: Alerta por número fiscal duplicado

Cuando tras la impresión de una **factura** existe más de un documento con el mismo `mf_invoice_number` (`has_printed`), `print_out_invoice` DEBE (MUST) devolver una acción de ventana en modo formulario sobre el modelo `sh.message.wizard`, con el mensaje del número repetido y la indicación de revisar las facturas anteriores en el contexto. Ese modelo no lo define este módulo ni aparece en sus dependencias, de modo que el aviso solo funciona en bases donde el módulo que lo provee esté instalado. `print_out_refund` y `print_debit_note` no ejecutan esta verificación.

#### Scenario: Secuencia fiscal repetida

- **WHEN** se imprime una factura y ya existía otro documento con la misma secuencia fiscal
- **THEN** se devuelve la acción de ventana sobre `sh.message.wizard` con ese número en el contexto

#### Scenario: Nota de crédito con secuencia repetida

- **WHEN** se imprime una nota de crédito cuyo número fiscal ya existe en otro documento
- **THEN** no se emite ningún aviso

### Requirement: Validaciones y datos de la nota de crédito fiscal

El método `check_print_out_refund` DEBE (MUST) rechazar la impresión cuando no hay máquina fiscal asignada, cuando la fecha del documento (`invoice_date_display`) no es la del día, o cuando el documento está en `draft` o `cancel`; y los datos enviados DEBEN (MUST) incluir el bloque de documento afectado con el número fiscal, el serial y la fecha (formato `dd/mm/aaaa`) del documento revertido (`reversed_entry_id`).

A diferencia de la factura, esta validación NO comprueba `mf_invoice_number`, por lo que una nota de crédito ya impresa puede volver a imprimirse y sobrescribir sus datos fiscales; tampoco comprueba que `reversed_entry_id` exista o tenga número fiscal, de modo que una NC sin asiento revertido falla al formatear la fecha del bloque afectado en lugar de emitir un error de validación.

#### Scenario: Nota de crédito de otro día

- **WHEN** se intenta imprimir una nota de crédito cuya fecha no es la de hoy
- **THEN** se lanza un error indicando que debe hacerse el mismo día

#### Scenario: Datos del documento afectado

- **WHEN** se imprime una nota de crédito de una factura fiscal
- **THEN** los datos enviados incluyen número, serial y fecha de la factura revertida

#### Scenario: Nota de crédito ya impresa

- **WHEN** se pulsa imprimir en una nota de crédito que ya tiene `mf_invoice_number`, del día y publicada
- **THEN** la validación la deja pasar y se construyen de nuevo los datos de impresión

### Requirement: Validaciones y datos de la nota de débito fiscal

El método `check_print_debit_note` DEBE (MUST) aplicar las mismas validaciones que la nota de crédito (máquina asignada, fecha del día, documento no borrador ni cancelado) y enviar como documento afectado el número fiscal, el serial y la fecha del documento de origen del débito (`debit_origin_id`).

#### Scenario: Nota de débito sin máquina asignada

- **WHEN** se intenta imprimir una nota de débito sin máquina fiscal asignada
- **THEN** se lanza un error de validación

### Requirement: Validaciones al marcar una factura como a crédito

Al cambiar el indicador `is_credit` de un documento, el sistema DEBE (MUST) rechazar el cambio si el documento ya tiene número fiscal (`mf_invoice_number`), y rechazar convertirlo a crédito cuando tiene pagos aplicados (`amount_residual` distinto de `amount_total`).

#### Scenario: Documento ya impreso

- **WHEN** se intenta cambiar `is_credit` en un documento con número fiscal
- **THEN** se lanza un error indicando que no se puede editar una factura ya impresa

### Requirement: Asignación del reporte Z a los documentos pendientes

El método `report_z` DEBE (MUST) rechazar la operación cuando la respuesta de la impresora no es válida, y en caso válido asignar a todos los documentos cuyo `mf_serial` coincida con el `_registeredMachineNumber` de la respuesta (el argumento `serial` recibido se descarta y se sobrescribe con ese valor) y que aún no tienen reporte Z (`mf_reportz` vacío) el valor del contador de cierre diario de la máquina (`_dailyClosureCounter`) incrementado en uno.

Si la máquina no devuelve el contador, la base la da `_get_z_and_add_one`, que devuelve el `mf_reportz` del primer documento del serial ordenado `mf_reportz desc` — orden **lexicográfico**, porque `mf_reportz` es un `Char`, de modo que "9" gana a "10" — o `0` si no hay ninguno. El método no incrementa pese a su nombre: el `+1` lo aplica `report_z`.

#### Scenario: Cierre Z con contador de la máquina

- **WHEN** se ejecuta el reporte Z y la impresora devuelve su contador de cierre diario
- **THEN** los documentos de ese serial sin reporte Z quedan con ese contador más uno

#### Scenario: Máquina sin contador y Z de distinta longitud

- **WHEN** la impresora no devuelve el contador de cierre diario y el serial tiene documentos con `mf_reportz` "9" y "10"
- **THEN** la base tomada es "9" y los documentos pendientes quedan con `mf_reportz = 10`

### Requirement: Método de pago fiscal en el widget de pagos

El método `_get_reconciled_info_JSON_values` DEBE (MUST) agregar a cada pago conciliado el campo `mf_payment_method` con el código de método de pago del diario de ese pago, para que la impresión fiscal y la interfaz dispongan del código.

#### Scenario: Factura con pagos conciliados

- **WHEN** se consulta la información de pagos conciliados de una factura
- **THEN** cada pago incluye el código de método de pago de su diario

### Requirement: Filtro de documentos fiscales en los libros

El asistente `wizard.accounting.reports` DEBE (MUST) exponer el indicador `with_fiscal_machine` (por defecto inactivo) que, al activarse, restringe el dominio a documentos con `mf_invoice_number`, `mf_reportz` y `mf_serial` establecidos, y agrega al libro de ventas las columnas "Reporte Z" y "Serial de Maquina" inmediatamente después del tipo de documento.

#### Scenario: Libro de ventas con máquina fiscal

- **WHEN** se genera el libro de ventas con `with_fiscal_machine` activo
- **THEN** solo se incluyen documentos impresos en máquina fiscal y el reporte agrega las columnas de reporte Z y serial

### Requirement: Sustitución del correlativo por el número fiscal en el libro de ventas

Con `with_fiscal_machine` activo, las líneas del libro de ventas DEBEN (MUST) omitir el campo `correlative` y usar como número de documento el `mf_invoice_number` (o `-` cuando falta), incluyendo el reporte Z y el serial de la máquina (o `-` cuando faltan) y, para las notas de crédito, el número fiscal del documento revertido.

#### Scenario: Línea de documento fiscal

- **WHEN** se emite una línea del libro de ventas de un documento impreso en máquina fiscal
- **THEN** el número de documento es el número fiscal y no se emite el correlativo

### Requirement: Resumen diario de ventas agrupado por reporte Z

Con `with_fiscal_machine` activo, el libro de ventas DEBE (MUST) agrupar los documentos por la **fecha de creación del registro** (`create_date`, formateada `%d-%m-%Y`) y luego por la combinación `mf_serial` + `mf_reportz`, ordenando cada grupo por `int(mf_invoice_number)`, y emitir líneas de resumen (identificadas con "RESUMEN", `partner_name` "Resumen Diario de Ventas", el rango "Desde … Hasta …" de números fiscales y alícuotas fijas 0,08 y 0,16) que acumulan las bases y montos por alícuota exenta, reducida y general. La fecha que se imprime en la línea de resumen sí es la del documento (`invoice_date_display`), por lo que un documento creado en un día distinto al de su fecha de factura DEBE (MUST) entenderse agrupado por la fecha de creación.

El cierre del acumulado no es uniforme:

- Facturas de diario de débito (`journal_id.is_debit`): se emiten como línea individual y el acumulado en curso se descarta **sin** emitir línea de resumen.
- Clientes con RIF de prefijo `J`, contribuyentes no ordinarios y notas de crédito: se emiten como línea individual, precedida de la línea de resumen solo si el acumulado difiere del monto del propio documento (`cumulative["amount_taxed"] != amounts["amount_taxed"]`); si coinciden, el resumen no se emite.
- Solo los documentos de tipo `out_invoice` / `out_refund` participan del recorrido; cualquier otro tipo se cuenta en el acumulado sin generar línea propia.

#### Scenario: Ventas a contribuyentes ordinarios consecutivas

- **WHEN** varias facturas creadas el mismo día, con igual serial y reporte Z, corresponden a contribuyentes ordinarios sin RIF de prefijo `J`
- **THEN** se emite una línea de resumen con el rango de números fiscales y los montos acumulados por alícuota

#### Scenario: Factura a persona jurídica con acumulado previo

- **WHEN** una de las facturas del grupo corresponde a un cliente con RIF de prefijo `J` y el acumulado en curso difiere del monto de esa factura
- **THEN** se emite primero la línea de resumen del acumulado y luego la factura como línea individual

#### Scenario: Factura de diario de débito en medio del grupo

- **WHEN** una factura del grupo pertenece a un diario de débito y hay montos acumulados de facturas anteriores
- **THEN** se emite solo su línea individual y el acumulado se reinicia sin emitir línea de resumen

### Requirement: Flujo de impresión desde el widget iot-mf-button

El widget `iot-mf-button` (registrado en `view_widgets`) DEBE (MUST) ejecutar la impresión en cuatro pasos: (1) llamar por RPC al método `check_<accion>` de `account.move` (`check_print_out_invoice`, `check_print_out_refund`, `check_print_debit_note`, `check_reprint`) con el id del documento; (2) reconstruir el `DeviceController` con el `iot_ip` y el `identifier` que devuelve ese payload; (3) enviar al dispositivo la acción con el nombre de la operación (`print_out_invoice`, `print_out_refund`, `print_debit_note` o `reprint`) y esperar el valor del evento de longpolling; (4) salvo en la reimpresión, llamar al método homónimo `print_*` del documento pasando ese valor tal cual —de donde se leen las claves de primer nivel `sequence` y `serial_machine`— y recargar la página.

El manejo de error de este flujo invoca `onIoTError`, una función que no está definida ni importada en el módulo, de modo que cualquier fallo capturado (por ejemplo la `ValidationError` de las validaciones previas) DEBE (MUST) entenderse como un `ReferenceError` en el navegador en lugar de una notificación al usuario.

#### Scenario: Impresión de factura exitosa

- **WHEN** el usuario pulsa "Print Invoice" y el dispositivo responde con secuencia y serial
- **THEN** se llama a `print_out_invoice` con ese valor y la página se recarga

#### Scenario: Reimpresión

- **WHEN** el usuario pulsa "Reprint Document" en un documento con número fiscal
- **THEN** se envía la acción `reprint` al dispositivo y no se llama a ningún método de persistencia ni se recarga la vista

#### Scenario: Validación rechazada por el backend

- **WHEN** `check_print_out_invoice` lanza una `ValidationError` (por ejemplo, factura de otra fecha)
- **THEN** el bloque de error intenta usar `onIoTError` y el fallo no llega al usuario como notificación

### Requirement: Reprogramación de la impresora al configurar el dispositivo

La acción `configure_device` del driver de la caja IoT DEBE (MUST), además de escribir los flags recibidos (`PJ21<flag_21>`, `PJ24<flag_24>` y `PJ77<show_version>` cuando la clave viene con valor no vacío — y `configure_device` del modelo siempre manda las tres, con `"00"` como valor apagado, así que las tres se escriben siempre), enviar siempre `PJ6300` y reprogramar la tabla de medios de pago de la impresora con una lista fija de 19 comandos `PE01`–`PE21` (efectivo, pago móvil, transferencias, PDV, crédito, divisas y Zelle), sobrescribiendo los nombres que la máquina tuviera programados. Al terminar devuelve `{"status": "true"}` como valor del evento.

#### Scenario: Configuración de un dispositivo fiscal

- **WHEN** se pulsa "Configure Device" en un dispositivo HKA con `flag_21 = "30"`, `flag_24 = "00"` y `show_version` inactivo
- **THEN** se envían `PJ2130`, `PJ2400`, `PJ7700`, `PJ6300` y los 19 comandos `PE..` de la lista fija, reemplazando los medios de pago programados en la impresora

### Requirement: Código fiscal por impuesto

El modelo `account.tax` DEBE (MUST) exponer el campo entero `fiscal_code` (por defecto `0`), que es el código de alícuota que se transmite a la impresora fiscal por cada línea.

#### Scenario: Impuesto con código fiscal configurado

- **WHEN** un impuesto tiene `fiscal_code` configurado y se usa en una línea de factura
- **THEN** ese código se envía a la impresora como alícuota de la línea

### Requirement: Solo lectura de los puertos fiscales

La ACL del modelo `iot.port` DEBE (MUST) otorgar únicamente permiso de lectura, sin escritura, creación ni eliminación desde la interfaz.

#### Scenario: Intento de crear un puerto desde la interfaz

- **WHEN** un usuario intenta crear o modificar un registro de `iot.port`
- **THEN** la ACL del módulo no lo permite
