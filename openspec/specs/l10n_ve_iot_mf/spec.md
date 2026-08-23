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

El modelo `iot.box` DEBE (MUST) exponer el indicador `has_fiscal_machine` con los puertos habilitados en `fiscal_port_ids`, y el indicador `blacklist` con los puertos vedados en `blacklist_port_ids`, ambos hacia el modelo `iot.port`.

#### Scenario: Caja con máquina fiscal declarada

- **WHEN** un administrador marca `has_fiscal_machine` en una caja IoT y le asigna puertos
- **THEN** esos puertos quedan registrados como puertos fiscales de esa caja

### Requirement: Publicación de los puertos fiscales a las cajas IoT

Los endpoints HTTP `/iot_fiscal/ports` y `/iot_blacklist/ports` DEBEN (MUST) devolver un JSON que mapea el identificador de cada caja IoT a la lista de nombres de sus puertos: el primero para las cajas con `has_fiscal_machine` activo y el segundo para las cajas con `blacklist` activo.

#### Scenario: Consulta de puertos fiscales

- **WHEN** una caja IoT consulta `/iot_fiscal/ports`
- **THEN** recibe un objeto JSON con el identificador de cada caja con máquina fiscal y los nombres de sus puertos habilitados

### Requirement: Identificación del fabricante por el nombre del dispositivo

El campo calculado `manufacturer_type` de `iot.device` DEBE (MUST) valer `HKA` cuando el nombre del dispositivo contiene "HKA", `PnP` cuando contiene "PnP", y quedar sin valor en cualquier otro caso.

#### Scenario: Dispositivo TFHKA

- **WHEN** el nombre del dispositivo contiene "HKA"
- **THEN** `manufacturer_type` es `HKA`

### Requirement: Registro del serial de la máquina fiscal en el dispositivo

El método `set_serial_machine` DEBE (MUST) guardar en `serial_machine` el número de máquina registrado que devuelve la impresora (`_registeredMachineNumber`) y renombrar el dispositivo al formato `<serial> - Fiscal Printer HKA`.

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

#### Scenario: Rango de números invertido

- **WHEN** se solicita una reimpresión por número con el número final menor que el inicial
- **THEN** se lanza un error indicando que el rango final es mayor que el inicial y no se envía nada a la impresora

#### Scenario: Reimpresión por fechas

- **WHEN** se solicita una reimpresión por fechas con un rango válido
- **THEN** los extremos se envían con formato `ddmmyy` junto al modo del tipo de documento

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

El documento contable DEBE (MUST) exponer la máquina fiscal en `iot_mf` (limitada por dominio a dispositivos con `serial_machine` establecido y tomando por defecto el primer dispositivo de tipo `fiscal_data_module`), su caja IoT en el campo relacionado `iot_box`, y los datos de la impresión fiscal en `mf_serial`, `mf_invoice_number` y `mf_reportz`, todos con seguimiento en el chatter y excluidos de la duplicación (`copy=False`).

#### Scenario: Documento nuevo en una instalación con una sola máquina

- **WHEN** se crea un documento contable y existe un dispositivo de tipo `fiscal_data_module`
- **THEN** ese dispositivo queda preseleccionado como máquina fiscal del documento

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

Los pagos enviados a la impresora DEBEN (MUST) llevar el código de método de pago del diario del pago (`account.journal.payment_method`, de dos caracteres, por defecto `01`) y su monto convertido multiplicando por `foreign_inverse_rate` cuando la moneda del pago no es VEF. Un documento sin pagos aplicados se envía con una única línea de pago de monto `0` y método `01`.

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

Cuando tras la impresión existe más de un documento con el mismo `mf_invoice_number` (`has_printed`), el sistema DEBE (MUST) abrir un aviso indicando el número repetido y pidiendo revisar las facturas anteriores.

#### Scenario: Secuencia fiscal repetida

- **WHEN** se imprime una factura y ya existía otro documento con la misma secuencia fiscal
- **THEN** se muestra un aviso con ese número y la indicación de revisar los documentos previos

### Requirement: Validaciones y datos de la nota de crédito fiscal

El método `check_print_out_refund` DEBE (MUST) rechazar la impresión cuando no hay máquina fiscal asignada, cuando la fecha del documento no es la del día, o cuando el documento está en `draft` o `cancel`; y los datos enviados DEBEN (MUST) incluir el bloque de documento afectado con el número fiscal, el serial y la fecha (formato `dd/mm/aaaa`) del documento revertido (`reversed_entry_id`).

#### Scenario: Nota de crédito de otro día

- **WHEN** se intenta imprimir una nota de crédito cuya fecha no es la de hoy
- **THEN** se lanza un error indicando que debe hacerse el mismo día

#### Scenario: Datos del documento afectado

- **WHEN** se imprime una nota de crédito de una factura fiscal
- **THEN** los datos enviados incluyen número, serial y fecha de la factura revertida

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

El método `report_z` DEBE (MUST) rechazar la operación cuando la respuesta de la impresora no es válida, y en caso válido asignar a todos los documentos de ese serial que aún no tienen reporte Z (`mf_reportz` vacío) el valor del contador de cierre diario de la máquina (`_dailyClosureCounter`) incrementado en uno. Si la máquina no devuelve el contador, se toma el mayor `mf_reportz` ya registrado para ese serial (o `0` si no hay ninguno) como base del incremento.

#### Scenario: Cierre Z con contador de la máquina

- **WHEN** se ejecuta el reporte Z y la impresora devuelve su contador de cierre diario
- **THEN** los documentos de ese serial sin reporte Z quedan con ese contador más uno

#### Scenario: Máquina sin contador de cierre

- **WHEN** la impresora no devuelve el contador de cierre diario
- **THEN** se usa como base el mayor reporte Z ya registrado para ese serial

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

Con `with_fiscal_machine` activo, el libro de ventas DEBE (MUST) agrupar los documentos por fecha y luego por la combinación de serial y reporte Z, ordenándolos por número fiscal, y emitir líneas de resumen (identificadas con "RESUMEN" y el rango "Desde … Hasta …" de números fiscales) que acumulan las bases y montos por alícuota exenta, reducida y general. Las facturas de clientes con RIF de prefijo `J`, los contribuyentes no ordinarios, las notas de crédito y las facturas de diarios de débito se emiten como líneas individuales y cierran el resumen acumulado en curso.

#### Scenario: Ventas a contribuyentes ordinarios consecutivas

- **WHEN** varias facturas del mismo día, serial y reporte Z corresponden a contribuyentes ordinarios sin RIF de prefijo `J`
- **THEN** se emite una línea de resumen con el rango de números fiscales y los montos acumulados por alícuota

#### Scenario: Factura a persona jurídica

- **WHEN** una de las facturas del grupo corresponde a un cliente con RIF de prefijo `J`
- **THEN** esa factura se emite como línea individual y el resumen acumulado en curso se cierra antes

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
