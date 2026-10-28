## Why

Caracas es UTC-4. A las 8:00 pm el reloj del servidor (UTC) ya marca el día siguiente. El código que usaba `fields.Date.today()` o `date_order.date()` (Datetime en UTC) buscaba la tasa de «mañana», que todavía no existe, y `compute_rate` lanzaba «no hay tasa asignada» aunque la tasa del día del usuario sí estaba cargada (se actualiza 3 veces al día). En la caja del POS, que busca con `raise_if_not_found=False`, la tasa quedaba en `0` sin avisar.

## What Changes

- `l10n_ve_sale`: helper `_l10n_ve_rate_date()` (igual al de la PR #1531) para convertir `date_order` a la fecha local; `binaural_account_asset` incorpora el fix de la PR #3134 (asientos de depreciación con la tasa del activo).
- `l10n_ve_rate`: `compute_rate` convierte un `datetime` con `fields.Date.context_today` y usa el «hoy» del usuario si la fecha llega vacía.
- Fuentes corregidas para usar `context_today`: `l10n_ve_sale` (orden, línea, factura desde la orden, facturas vencidas), `l10n_ve_pos` (`pos.config`), `l10n_ve_accountant` (`account.move`, `account.payment`), `l10n_ve_igtf` (utilidades de conversión), `l10n_ve_payment_extension` (línea de retención y defaults de los wizards de retención IVA/ISLR), `l10n_ve_suggested_amount`, `l10n_ve_fiscal_lock_days`, `l10n_ve_accountant/wizard/invoices_details`.
- Los defaults de los wizards (`date.today().replace(day=1)`) se evaluaban al importar el módulo y quedaban fijos hasta reiniciar: ahora son `lambda` con `context_today`.
- integra-addons: `binaural_purchase`, `binaural_payment`, `binaural_foreign_cost`, `binaural_last_cost`, `binaural_clinics_sale` (sin cambios), `binaural_appointment`, `binaural_invoice_lots`, `binaural_stock_advance`, `binaural_stock_landed_foreign_costs`, `binaural_mobile_igtf`, `binaural_website_sale`. `binaural_mobile` y `binaural_advance_payment` quedan sin tocar por decisión del equipo.

## Impact

- Specs afectadas: `l10n_ve_rate`, `l10n_ve_sale`, `l10n_ve_pos`, `l10n_ve_accountant`, `l10n_ve_igtf`, `l10n_ve_payment_extension`, `binaural_purchase`, `binaural_payment`, `binaural_mobile_igtf`.
- Pendiente de decisión: en controladores públicos o `sudo()` sin zona horaria en el usuario, `context_today` cae a UTC. Habría que respaldarse en la zona horaria de la compañía.
- No se tocó nómina, reportes, el cron de `l10n_ve_stock_account` ni el filtro de listas de precios del POS.
