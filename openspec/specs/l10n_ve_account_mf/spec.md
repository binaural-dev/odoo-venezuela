# l10n_ve_account_mf

## Purpose

Integra las impresoras fiscales TFHKA con Facturación/Contabilidad vía Web Serial API (driver de `l10n_ve_mf_base`), sin dependencia del stack IoT. Extiende `account.move`, `account.journal`, `account.tax`, `res.company` y `res.config.settings`; agrega botones de impresión fiscal en el formulario de factura, un systray de conexión, el Fiscalizador (herramienta de diagnóstico) y el wizard de reportes de máquina fiscal. Depende de `account`, `web`, `l10n_ve_mf_base`, `l10n_ve_invoice` (aporta `is_debit_journal`, `correlative`, `prefix_vat`), `l10n_ve_accountant` y `l10n_ve_stock_account` (botón de forma libre `print_invoice_free_form`). Puede convivir con `l10n_ve_pos_mf` compartiendo campos.

## Requirements

### Requirement: Tipo de impresión de factura por compañía

La compañía DEBE (MUST) poder configurar `invoice_print_type` (`free` = forma libre, default; `fiscal` = máquina fiscal) desde ajustes (campo related en `res.config.settings`, `readonly=False`). En el formulario de factura, los botones de máquina fiscal solo son visibles cuando el related `print_type` es `fiscal` y `correlative` está vacío, mientras que el botón de forma libre `print_invoice_free_form` (de `l10n_ve_stock_account`) solo es visible cuando `print_type` es `free` y hay `correlative`.

#### Scenario: Compañía en modo fiscal

- **WHEN** la compañía tiene `invoice_print_type = "fiscal"` y se abre una factura de cliente publicada sin número fiscal ni correlativo
- **THEN** se muestra el botón "Imprimir Factura (MF)" y no el de impresión en forma libre

#### Scenario: Compañía en forma libre

- **WHEN** la compañía tiene `invoice_print_type = "free"`
- **THEN** los botones MF no aparecen y la impresión en forma libre aplica con normalidad

### Requirement: Configuración del Flag 21 por compañía

La compañía DEBE (MUST) poder configurar `mf_flag_21` (selección `00`/`01`/`02`/`30`, default `00`) desde ajustes; `_get_mf_flag21()` lo incluye en el payload de impresión para que el driver de `l10n_ve_mf_base` formatee montos, cantidades y pagos con esa configuración.

#### Scenario: Flag configurado

- **WHEN** la compañía tiene `mf_flag_21 = "30"` y se construye el payload de una factura
- **THEN** el payload trae `flag_21 = "30"`

### Requirement: Validaciones para imprimir una factura fiscal

`check_print_out_invoice()` DEBE (MUST) rechazar con `ValidationError` la impresión cuando: la factura ya tiene `mf_invoice_number`; el estado es `draft` o `cancel`; la fecha de la factura no es el día actual según la zona horaria del usuario (`fields.Date.context_today`); o la factura es a crédito (`is_credit`) y tiene pagos asociados (`amount_residual != amount_total`). Una factura sin líneas devuelve `{"valid": False}` con mensaje.

#### Scenario: Factura ya impresa

- **WHEN** se intenta imprimir una factura que ya tiene `mf_invoice_number`
- **THEN** se lanza un error indicando que ya fue impresa

#### Scenario: Fecha distinta al día actual

- **WHEN** la fecha de la factura no coincide con la fecha de hoy en la zona horaria del usuario
- **THEN** se lanza un error y no se construye el payload

### Requirement: Bloqueo de edición de factura a crédito

El onchange de `is_credit` DEBE (MUST) impedir marcar/desmarcar el campo cuando la factura ya tiene `mf_invoice_number` (documento impreso en papel), y impedir convertirla a crédito cuando tiene pagos asociados (`amount_residual != amount_total`).

#### Scenario: Factura impresa

- **WHEN** se cambia `is_credit` en una factura con número fiscal
- **THEN** se lanza un error indicando que no puede editarse una factura impresa

### Requirement: Construcción del payload de impresión

El payload de impresión DEBE (MUST) construirse con: el cliente en formato `prefix_vat-vat`, nombre normalizado (NFKD sin acentos ni caracteres especiales vía `_normalize_product_name`), dirección y teléfono; líneas de producto con `fiscal_code` del primer impuesto (`account.tax.fiscal_code`, 0 sin impuestos), precio expresado en VEF (usa `foreign_price` cuando la moneda de la compañía no es VEF) con el descuento porcentual de línea ya aplicado; y pagos tomados del widget de pagos, mapeando cada uno al código del diario (`account.journal.payment_method`, default `01`) y convirtiendo a VEF con `foreign_inverse_rate` los pagos en otra moneda. Sin pagos registrados se envía una línea `{amount: 0, payment_method: "01"}`.

#### Scenario: Factura en moneda extranjera con descuento de línea

- **WHEN** la compañía no opera en VEF y una línea tiene 10% de descuento
- **THEN** la línea del payload usa `foreign_price * 0.9` como precio unitario

#### Scenario: Pago en moneda distinta a VEF

- **WHEN** un pago del widget está en una moneda distinta de VEF
- **THEN** su monto se multiplica por `foreign_inverse_rate` de la factura

### Requirement: Persistencia de los datos fiscales y advertencia de duplicado

Tras una impresión exitosa, `print_out_invoice(values)` DEBE (MUST) escribir `mf_invoice_number`, `mf_serial` y (si viene) `mf_reportz` en la factura; si el número fiscal ya existe en otra factura (`has_printed`, búsqueda con más de un resultado), DEBE (MUST) publicar la advertencia en el chatter y devolver una notificación sticky de tipo warning (`display_notification`). Los tres campos son `copy=False` y con tracking.

#### Scenario: Impresión con número único

- **WHEN** el driver devuelve secuencia, serial y reporte Z
- **THEN** los tres campos quedan persistidos en la factura

#### Scenario: Número fiscal duplicado

- **WHEN** el número devuelto ya existe en otra factura
- **THEN** se publica el aviso en el chatter y el usuario recibe una notificación sticky de advertencia

### Requirement: Nota de crédito exige factura original con datos fiscales

`check_print_out_refund()` DEBE (MUST) validar que la NC no esté impresa, sea del día actual, esté publicada y que `reversed_entry_id` exista y tenga `mf_invoice_number`; el bloque `invoice_affected` se construye con el número fiscal, `mf_serial` y la fecha de la factura original en formato `DD/MM/YYYY`. Para NC originadas en POS (existe un `pos.order` vinculado al move actual o al revertido), los pagos DEBEN (MUST) tomarse de los pagos reales de la orden con su `code_fiscal_printer`, para conservar la separación por método fiscal; en caso contrario se usan los pagos del widget en valor absoluto.

#### Scenario: Factura original sin número fiscal

- **WHEN** la factura revertida no tiene `mf_invoice_number`
- **THEN** se lanza un error y la NC no se imprime

#### Scenario: NC de una orden POS

- **WHEN** existe una orden POS vinculada con pagos registrados
- **THEN** las líneas de pago del payload provienen de `pos.order.payment_ids` con el código fiscal de cada método

### Requirement: Nota de débito con factura de origen

`check_print_debit_note()` DEBE (MUST) validar que la ND no esté impresa, sea del día actual, esté publicada y que `debit_origin_id` exista con `mf_invoice_number`, construyendo `invoice_affected` desde la factura de origen. El botón "Imprimir ND (MF)" solo es visible en facturas de diario de débito (`is_debit_journal` de `l10n_ve_invoice`).

#### Scenario: ND válida

- **WHEN** la ND publicada del día tiene un origen con número fiscal
- **THEN** el payload incluye `invoice_affected` con número, serial y fecha DD/MM/YYYY del origen y el driver imprime vía `printDebitNote`

### Requirement: Reimpresión del documento actual

`check_reprint()` DEBE (MUST) rechazar la reimpresión si la factura no tiene `mf_invoice_number` y devolver `type` (move_type), `mf_number` e `is_debit_note` para que el frontend reimprima vía `TfhkaDriver.reprintDocument`. El botón "Reimprimir (MF)" solo es visible cuando el documento ya tiene número fiscal.

#### Scenario: Documento nunca impreso

- **WHEN** se solicita reimprimir una factura sin número fiscal
- **THEN** se lanza un error indicando que aún no fue impresa

### Requirement: Registro de fallos de impresión en el chatter

`log_mf_print_failure(action, reason)` DEBE (MUST) publicar en el chatter de la factura un mensaje con la acción fallida (Factura, Nota de crédito, Nota de débito o Reimpresión) y el detalle del motivo. El frontend lo invoca ante navegador sin soporte Web Serial, falta de conexión o error del driver, sin bloquear el flujo si el registro falla.

#### Scenario: Impresión sin conexión

- **WHEN** la impresión falla porque no hay máquina fiscal conectada
- **THEN** el chatter de la factura registra el intento fallido con la acción y el motivo

### Requirement: Flujo de impresión desde el formulario de factura

El widget `mf-webserial-button` DEBE (MUST) ejecutar el flujo en tres pasos: (1) llamar al método `check_*` correspondiente en `account.move` para validar y obtener el payload; (2) garantizar la conexión Web Serial — reconexión silenciosa primero y, si falla, prompt de autorización de puerto (`requestPermission: true`) — y traducir el payload al formato del driver (líneas con `fiscal_code` sin prefijo `t`, pagos con código a 2 dígitos en valor absoluto, líneas `info` opcionales como `additional_lines`); (3) persistir el resultado con el método `print_*` y recargar la vista. Si el navegador no soporta Web Serial, la conexión falla o el driver devuelve error, DEBE (MUST) notificar el error y registrar el fallo en el chatter sin persistir nada.

#### Scenario: Impresión exitosa

- **WHEN** el usuario pulsa "Imprimir Factura (MF)" y el driver responde con éxito
- **THEN** se llama a `print_out_invoice` con `{valid, data: {sequence, serial_machine, mf_reportz}}` y la página se recarga

#### Scenario: Driver reporta error

- **WHEN** `printInvoice` devuelve `success: false`
- **THEN** no se llama al método de persistencia y el error queda notificado y registrado en el chatter

### Requirement: Sincronización del Reporte Z con las facturas pendientes

`account.move.report_z(serial, response)` DEBE (MUST) lanzar un error si `response.valid` es falso, y en caso contrario asignar `mf_reportz = contador + 1` a todas las facturas del serial (`_registeredMachineNumber`) que aún no tienen Z (`mf_reportz = False`), usando el `_dailyClosureCounter` recibido o, si falta, el último Z registrado en facturas de ese serial (`_get_z_and_add_one`, que devuelve 0 si no hay historial).

#### Scenario: Z impreso con contador

- **WHEN** el frontend llama a `report_z` con el S1 leído tras imprimir el Z (contador N)
- **THEN** todas las facturas pendientes de ese serial quedan con `mf_reportz = N + 1`

#### Scenario: Contador no recuperado

- **WHEN** el S1 no trae `_dailyClosureCounter`
- **THEN** se usa el mayor `mf_reportz` ya registrado para ese serial como base

### Requirement: Wizard de reportes de máquina fiscal

El wizard `l10n_ve.mf.reports.wizard` (menú "Reportes Maquina Fiscal" bajo Detalle de Ventas de `l10n_ve_accountant`) DEBE (MUST) ofrecer cuatro operaciones vía Web Serial: Reporte X (`I0X`, sin confirmación); Reporte Z con diálogo de confirmación explícito y posterior sincronización (`_readS1Data` + llamada a `account.move.report_z`); impresión de resumen por rango de fechas (comando `I2S<desde><hasta>` en formato DDMMYY, timeout 30s); y reimpresión de facturas por rango de fechas (comando `Rf<desde><hasta>` con los valores rellenados a 7 posiciones, timeout 60s). El rango DEBE (MUST) validarse con `date_to >= date_from` (tanto en el wizard como en el frontend) y las fechas del formulario se aceptan en múltiples formatos (YYYY-MM-DD, DD/MM/YYYY, Date, DateTime de Luxon).

#### Scenario: Reporte Z desde el wizard

- **WHEN** el usuario confirma "Imprimir Reporte Z" con la impresora conectada
- **THEN** se envía `I0Z`, se lee el S1 y se llama a `account.move.report_z` con el serial y el contador

#### Scenario: Rango de fechas invertido

- **WHEN** `date_to` es anterior a `date_from`
- **THEN** se lanza un error y no se envía ningún comando

#### Scenario: Z sin sincronización posible

- **WHEN** el Z se imprime pero el S1 posterior no se puede leer
- **THEN** se notifica una advertencia indicando que Odoo no quedó sincronizado

### Requirement: Systray de estado de conexión

El backend DEBE (MUST) mostrar un ítem de systray con el estado de la conexión Web Serial (desconectada/conectando/conectada/error): al cargar la página intenta la reconexión silenciosa a un puerto ya autorizado y verifica que la impresora responda al ENQ; el click conecta manualmente — intento silencioso primero y luego prompt de autorización de puerto (`requestPermission: true`) — o desconecta si ya estaba conectada; y el estado se re-sincroniza con el driver compartido cada 5 segundos para reflejar conexiones hechas por otros componentes.

#### Scenario: Reconexión al cargar

- **WHEN** se carga el backend y existe un puerto previamente autorizado que responde al ENQ
- **THEN** el ícono pasa a conectado sin interacción del usuario

#### Scenario: Primera autorización desde el systray

- **WHEN** el usuario hace click estando desconectado y no hay puerto autorizado
- **THEN** se dispara el prompt de selección de puerto de Web Serial

### Requirement: Fiscalizador (herramienta de diagnóstico)

El módulo DEBE (MUST) registrar en el menú de Developer Tools (registry `debug`) el ítem "Fiscalizador MF" que abre un diálogo con acciones técnicas: conectar, estado (ENQ con STS1 y errores), datos S1 (serial, RIF, últimos números y contador Z), medios de pago (S4), Info IGTF, Reporte X, Reporte Z (con confirmación y sincronización de `report_z`) y envío de comando raw, registrando cada resultado en una bitácora con hora. La acción "Info IGTF (S3+S25)" DEBE (MUST) mostrar la tasa IGTF programada y los flags de sistema (S3), el desglose del documento en curso (S25) y clasificar los medios de pago del S4 en nacionales (01-19) vs divisa (20-24), advirtiendo cuando no hay medios en divisa programados.

#### Scenario: Diagnóstico IGTF

- **WHEN** el usuario pulsa "Info IGTF (S3+S25)" con la impresora conectada
- **THEN** la bitácora muestra la tasa IGTF, los flags crudos del S3, el desglose S25 y el conteo de medios nacionales vs divisa

#### Scenario: Impresora sin medios en divisa

- **WHEN** el S4 no contiene métodos con código 20-24
- **THEN** se registra la advertencia de que deben programarse para cobrar en divisas

### Requirement: Código de método de pago fiscal en el diario

`account.journal` DEBE (MUST) tener el campo `payment_method` (Char de 2 caracteres, default `01`) editable en el formulario del diario, que mapea el diario al código de método de pago TFHKA (01-19 nacional, 20-24 divisas/IGTF) usado al construir las líneas de pago.

#### Scenario: Diario de divisas

- **WHEN** un diario se configura con `payment_method = "20"` y un pago de la factura usa ese diario
- **THEN** la línea de pago del payload lleva el código `20`

### Requirement: Coexistencia con l10n_ve_pos_mf

Los campos compartidos DEBEN (MUST) definirse con los mismos nombres y semántica que en `l10n_ve_pos_mf` — `mf_invoice_number`, `mf_serial`, `mf_reportz` en `account.move` y `fiscal_code` (Integer, default 0) en `account.tax` — para que Odoo fusione las definiciones cuando ambos módulos están instalados, y `l10n_ve_pos_mf` encadena su override de `report_z` sobre esta implementación vía `super`.

#### Scenario: Ambos módulos instalados

- **WHEN** `l10n_ve_account_mf` y `l10n_ve_pos_mf` están instalados juntos
- **THEN** una impresión desde cualquiera de los dos escribe en los mismos campos de `account.move`, y `report_z` actualiza tanto facturas como pedidos POS pendientes
