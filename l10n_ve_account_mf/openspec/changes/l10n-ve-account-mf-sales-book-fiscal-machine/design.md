## Contexto

Dos formas de que una venta llegue al Libro de Ventas en Venezuela:
1. Factura con número de control (forma libre / contingencia): Odoo asigna
   `correlative`; sale línea por línea en el libro general.
2. Venta por máquina fiscal: el número lo emite la máquina; la factura queda sin
   `correlative` y con `mf_serial` / `mf_invoice_number` / `mf_reportz`. Se
   reporta como Resumen Diario de Ventas por Reporte Z.

El libro general excluye el caso 2 con el filtro
`("correlative","not in",['/',False])`.

## Decisión

Portar la extensión que en V17 traía `l10n_ve_iot_mf` al módulo V19
`l10n_ve_account_mf`, porque:
- Está instalado en las BD afectadas (p.ej. 212).
- Depende de `l10n_ve_invoice`, así que puede heredar el wizard y su vista.
- Define los campos `mf_serial`/`mf_invoice_number`/`mf_reportz` en
  `account.move`, así que la extensión es autosuficiente.
- Es semánticamente el módulo de facturación con máquina fiscal (Web Serial),
  sucesor del `l10n_ve_iot_mf` (IoT) que se desinstaló en la migración.

NO se elige `l10n_ve_pos_mf` porque no depende de `l10n_ve_invoice` (diseño
autónomo) y no podría heredar el wizard general sin una dependencia artificial.

## Adaptaciones respecto a V17 / V19-iot

- El wizard base de V19 fue refactorizado: usa `invoice_date_display` (no
  `invoice_date`), `taxpayer_type` (no `taxpayer`), y las columnas del libro se
  arman por grupos (`_get_sale_book_field_groups`) con claves `invoice_number` /
  `credit_note_number` / `debit_note_number` / `correlative` (ya no existe
  `document_number`).
- Por eso la línea de resumen usa `invoice_number` para el rango
  "Desde X Hasta Y" (en V19-iot iba a `document_number`, columna inexistente →
  no se mostraba: se corrige aquí).
- Se añade la alícuota adicional (31%) al acumulado del resumen (V19-iot solo
  acumulaba 16% y 8%).
- Se añade columna "N° Máquina Fiscal" (mf_invoice_number), que en V19-iot no
  llegaba a mostrarse.

## Alternativas descartadas

- Reinstalar `l10n_ve_iot_mf`: se quitó a propósito en la migración a Web
  Serial; reintroduce el stack IoT. Descartado.
- Menú al reporte viejo `wizard.sales.book` de `l10n_ve_pos_mf`: es un reporte
  distinto y paralelo; deja dos "libros de ventas" compitiendo. Se descartó y
  se revirtió el intento previo.
- Cambiar `invoice_print_type` a `free`: incorrecto para una tienda que factura
  con máquina fiscal (confirmado: 212 usa máquina fiscal).
