## Why

Contabilidad → Reportes → Detalle de ventas fallaba con `ValueError: Expected singleton: res.currency(2, 1)` en cuanto había facturas en más de una moneda (ticket #16382). `_compute_detailed_amounts` formateaba con `self.currency_id`, el recordset completo del lote, en vez de `record.currency_id`. Al corregirlo salieron otros fallos del reporte, escrito con las claves de Odoo 16: `tax_totals` ya no trae `amount_total`, `amount_untaxed` ni `formatted_amount_total`; el estado `posted` ya no existe en los pagos; y los totales sumaban montos de monedas distintas como si fueran una sola.

## What Changes

- `l10n_ve_accountant`: `_compute_detailed_amounts` formatea con la moneda de cada factura; los impuestos salen de `tax_totals['tax_amount_currency']` (antes siempre 0) y `gross_discount_amount` es el bruto menos el descuento (antes guardaba el bruto).
- Reporte `account.invoices.details`: el total del documento usa `total_amount_currency` / `formatted_total_amount_currency`; los pagos se filtran con `state in (in_process, paid)` (antes `posted`, que ya no existe, así que la sección salía vacía).
- Facturas y pagos se agrupan por moneda dentro de cada plazo y diario, cada grupo con su subtotal en esa moneda sin convertir. El reporte cierra con el total general de ventas y de pagos en la moneda de la compañía (tasa de cada documento: `tax_totals['total_amount']` y `amount_company_currency_signed`).
- Prueba `TestInvoiceDetailsReport`.

## Impact

- Specs afectadas: `l10n_ve_accountant` (nuevo requisito: el Detalle de ventas agrupa por moneda y cierra en la moneda de la compañía).
- Código: `l10n_ve_accountant/models/account_move.py`, `l10n_ve_accountant/report/account_invoice_details_report.py`, `l10n_ve_accountant/report/account_invoice_details.xml`. Versión del manifest 19.0.1.0.45.
- Sin migración ni cambios de datos: el reporte se recalcula al imprimir. Sin cadenas nuevas para `es_VE.po` (se reutilizan las existentes).
