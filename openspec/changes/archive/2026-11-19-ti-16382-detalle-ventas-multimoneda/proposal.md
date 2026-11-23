## Why

Contabilidad → Reportes → Detalle de ventas fallaba con `ValueError: Expected singleton: res.currency(2, 1)` en cuanto había facturas en más de una moneda (ticket #16382). `_compute_detailed_amounts` formateaba con `self.currency_id`, el recordset completo del lote, en vez de `record.currency_id`. Al corregirlo salieron otros fallos del reporte, escrito con las claves de Odoo 16: `tax_totals` ya no trae `amount_total`, `amount_untaxed` ni `formatted_amount_total`; el estado `posted` ya no existe en los pagos; y los totales sumaban montos de monedas distintas como si fueran una sola.

## What Changes

- `l10n_ve_accountant`: `_compute_detailed_amounts` formatea con la moneda de cada factura; los impuestos salen de `tax_totals['tax_amount_currency']` (antes siempre 0) y `gross_discount_amount` es el bruto menos el descuento (antes guardaba el bruto).
- Reporte `account.invoices.details`: el total del documento usa `total_amount_currency` / `formatted_total_amount_currency`; los pagos se filtran con `state in (in_process, paid)` (antes `posted`, que ya no existe, así que la sección salía vacía).
- Facturas y pagos se agrupan por moneda dentro de cada plazo y diario, cada grupo con su subtotal en esa moneda sin convertir. El reporte cierra con el total general de ventas y de pagos en la moneda de la compañía (tasa de cada documento: `tax_totals['total_amount']` y `amount_company_currency_signed`).
- `_compute_detailed_amounts` salta (`continue`, antes `return`) los documentos sin `tax_totals`, para no dejar sin calcular el resto del lote.
- `l10n_ve_invoice`: `_get_effective_discount_percent()` devuelve el % exacto de `discount_fixed` cuando la compañía descuenta por monto fijo; sin esto el Detalle de ventas mostraba el descuento en 0.
- Pruebas `TestInvoiceDetailsReport` (16 casos) y 2 casos nuevos en `TestAccountMoveLineFixedDiscount`.

## Impact

- Specs afectadas: `l10n_ve_accountant` (nuevo requisito: el Detalle de ventas agrupa por moneda y cierra en la moneda de la compañía) y `l10n_ve_invoice` (escenario del descuento efectivo con descuento fijo).
- Código: `l10n_ve_accountant/models/account_move.py`, `l10n_ve_accountant/report/account_invoice_details_report.py`, `l10n_ve_accountant/report/account_invoice_details.xml`, `l10n_ve_invoice/models/account_move_line.py`. Versiones del manifest: `l10n_ve_accountant` 19.0.1.0.46 y `l10n_ve_invoice` 19.0.1.0.30.
- Sin migración ni cambios de datos: el reporte se recalcula al imprimir. 2 cadenas nuevas en `es_VE.po` ("Total Sales (" y "Total Payments ("); se quita "<strong>Total Sales</strong>".
