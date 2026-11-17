# Fix: la nota de débito se identifica por el documento y no solo por el diario

## Why

Ticket Helpdesk #16372 (https://www.binauraldev.com/odoo/all-tickets/16372). Minuta de Sumiflex del
19/10/2026; reproducido en su staging el 10/11/2026. Mismo origen que #16258 (Ganchos Venezolanos), que se resolvió por configuración.

La nota de débito nativa (`account.debit.note`) nace en el MISMO diario que su factura de origen. En
compras ese diario tiene `is_debit = False`, y el comprobante de retención, el PDF estándar, el TXT de
retenciones de IVA y los libros decidían "es ND" con `journal_id.is_debit`: la ND de proveedor salía como
factura (`01-REG`, número en "Factura", sin factura afectada, título "Factura de proveedor"). Las notas de
crédito no tenían el problema porque se identifican por `move_type`.

## What Changes

- `account.move._is_debit_note()` (`l10n_ve_invoice`): ND si tiene `debit_origin_id` o su diario es
  `is_debit`; una nota de crédito nunca lo es.
- Reemplaza `journal_id.is_debit` por `_is_debit_note()` en:
  - comprobante de retención de IVA (`retention_voucher_templates.xml`, 4 columnas),
  - TXT de retenciones de IVA (`wizard_retention_iva.py`),
  - libros de compras y ventas y su TXT (`accounting_reports.py`: tipo FAC/ND, tipo de transacción,
    factura afectada),
  - formato libre de factura (`report_invoice_free_form.xml`).
- PDF estándar: herencia de `account.report_invoice_document` que rotula "Nota de débito de proveedor" a la
  ND de proveedor (`report_invoice_debit_note_title.xml`, traducción en `es_VE.po`).
- Pruebas que quedaban en error por falta de tasa (`compute_rate` solo usa la fecha exacta):
  `l10n_ve_invoice/tests/common.py::ForeignRateFixture`, aplicado a 6 clases de `l10n_ve_invoice` y 3 de
  `l10n_ve_invoice_digital`. En `l10n_ve_invoice_digital`, `_create_retention` usa la vista de IVA (la línea
  nace con su alícuota; `_check_iva_lines_have_aliquot` rechaza 0%).
- `l10n_ve_igtf` (`views/account_move.xml`): los cuatro `xpath` que reemplazan las alertas de "créditos/débitos
  pendientes" del núcleo identifican cada alerta por su condición `invisible` y no por posición. Ver la sección
  "Alertas de IGTF" más abajo: no es parte de las notas de débito, es un defecto que apareció al correr las
  pruebas de los módulos dependientes.
- Bump de versión: `l10n_ve_invoice` `19.0.1.0.29`, `l10n_ve_payment_extension` `19.0.2.2.9`, `l10n_ve_igtf` `19.0.1.2.23`,
  `l10n_ve_invoice_digital` `19.0.1.4.9` (pruebas arregladas).

## Decisiones

- **Detectar al imprimir, por el documento**, no guardar `in_debit` en `invoice_type`/`type` de la
  retención: cubre los tres caminos de creación (a mano con `Form`, automática al publicar con
  `generate_iva_retention`, asistente de pago) y corrige también las retenciones ya emitidas.
- **El signo del pago no cambia**: la ND de proveedor suma deuda como la factura (`outbound`); solo la nota
  de crédito se invierte. `_prepare_payment_vals` ya decide por el documento.
- **`is_debit_journal` (campo almacenado) no se toca**: lo usan las vistas y las máquinas fiscales.
- **Alcance también en ventas**: una ND de cliente con `debit_origin_id` en un diario normal sale como ND en
  los libros y el comprobante.

## Alertas de IGTF (`l10n_ve_igtf`, fuera del tema de las notas de débito)

**Qué pasaba.** `l10n_ve_igtf` reemplaza las cuatro alertas nativas de "tiene créditos/débitos pendientes"
(factura y nota de crédito, de cliente y de proveedor) por una variante que también menciona los anticipos.
Lo hacía así:

    //div[hasclass('alert', 'alert-info')][1]   [2]   [3]   [3]

Eso asume que los cuatro primeros `alert-info` del formulario son los del núcleo. Si cualquier otro módulo
agrega un `alert-info` ANTES de ellos, el índice se corre: el primer `xpath` reemplaza el aviso del otro módulo
y los demás caen un lugar más abajo. El resultado es que se pierde el aviso ajeno y las variantes de IGTF
quedan en el div equivocado (en la vista combinada hay condiciones repetidas y una alerta sin reemplazar).

**Dónde se vio.** `l10n_ve_sale` agrega, justo después del `header`, el aviso "este documento usa la tasa de su
orden de venta" (ajuste de la compañía "usar la tasa de la orden en la factura"). Con `l10n_ve_igtf` instalado
ese aviso no aparecía y fallaban 3 pruebas de `l10n_ve_sale` (`TestSaleOrderRateDateForm`), también en
`maintenance-19.0` sin estos cambios. Con `l10n_ve_sale` solo, o con otros módulos sin IGTF, pasaban.

**Por qué no hay una relación directa entre los módulos.** `l10n_ve_igtf` no depende de `l10n_ve_sale` ni al
revés. El defecto está en cómo IGTF se engancha a la vista base de `account.move`: le pasaría a cualquier módulo
que inserte un `alert-info` antes de las alertas del núcleo. `l10n_ve_sale` es solo el primero que lo hizo.

**Qué cambia.** Cada `xpath` toma su alerta por la condición `invisible` del núcleo
(`move_type not in ('out_invoice', 'out_receipt')`, `... ('in_invoice', 'in_receipt')`,
`move_type != 'out_refund'`, `move_type != 'in_refund'`) junto con `invoice_has_outstanding`, sin importar
cuántos `alert-info` haya antes. Solo cambia a cuál div se aplica cada reemplazo; el contenido de las alertas de
IGTF no cambia.

**Cómo se garantiza (sin depender de `l10n_ve_sale`).**
`l10n_ve_igtf/tests/test_account_move_alert_views.py` crea en la prueba la vista de un tercero que inserta su
`alert-info` después del `header`, como hija de la vista de `l10n_ve_accountant` (así se aplica antes que la de
IGTF, igual que la de `l10n_ve_sale`), y comprueba sobre la vista combinada que:

- el aviso del tercero sigue en la vista, y
- hay exactamente cuatro alertas de pendientes, una por tipo de documento, y cada una es la variante de IGTF.

Con los `xpath` posicionales originales las dos pruebas fallan (aviso perdido; 5 alertas en vez de 4). Con los
nuevos pasan.

**Límites.** No se vio en el navegador; se comprobó sobre la vista combinada (`get_view`). Las pruebas de
`l10n_ve_sale` siguen siendo las que cubren el aviso de la tasa de la orden con IGTF instalado.

## Non-goals

- `l10n_ve_iot_mf` y `l10n_ve_account_mf` (impresión fiscal) siguen leyendo `journal_id.is_debit`.
- Las dos fechas del ticket (ND A798 con fecha 06/08, ND de cliente 00092780 con fecha contable) quedan por
  confirmar con el cliente.
- ISLR y municipal: sus comprobantes no tienen columnas de ND.

## Tests

`l10n_ve_igtf/tests/test_account_move_alert_views.py` (2 pruebas): alertas de IGTF sin depender de la posición.

`l10n_ve_payment_extension/tests/test_debit_note_detection.py` (15 pruebas): retención a mano con `Form` y
automática al publicar, líneas intercaladas de facturas, NDs y NC, ND de cliente, diario `is_debit`, signo del
pago, TXT, libro de compras, título del PDF estándar y del formato libre.
