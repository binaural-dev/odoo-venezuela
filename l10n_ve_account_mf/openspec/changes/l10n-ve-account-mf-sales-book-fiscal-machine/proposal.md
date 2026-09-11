## Why

En compañías con `invoice_print_type = 'fiscal'`, las facturas emitidas por
máquina fiscal (incluidas las del PdV) NO llevan número de control
(`correlative`): en ese modo `l10n_ve_invoice` no lo asigna, porque el número
lo emite físicamente la máquina. El Libro de Ventas/Compras general
(`wizard.accounting.reports`) filtra con `("correlative","not in",['/',False])`
y por eso descarta todos esos documentos. En la BD de producción 212
(INVERSIONES MERCEBAR / 2doce), 204 de 213 facturas del PdV en 60 días no
aparecen en el libro.

En V17 esto se resolvía con dos opciones en el mismo wizard, aportadas por
`l10n_ve_iot_mf`: "Con máquina fiscal" y "Incluir todos los documentos
emitidos". En V19 `l10n_ve_iot_mf` fue desinstalado (migración IoT → Web
Serial), así que esas opciones desaparecieron. El nuevo módulo de facturación
fiscal por Web Serial es `l10n_ve_account_mf` (instalado, depende de
`l10n_ve_invoice` y define `mf_serial`/`mf_invoice_number`/`mf_reportz`), que
es el hogar correcto para portar esa extensión.

## What Changes

- `wizards/accounting_reports.py`: hereda `wizard.accounting.reports` y añade
  dos campos:
  - `with_fiscal_machine` ("Con máquina fiscal"): SOLO documentos de máquina
    fiscal, presentados como Resumen Diario de Ventas agrupado por Reporte Z.
  - `all_documents` ("Incluir todos los documentos emitidos"): TODOS los
    documentos (forma libre + máquina fiscal), línea por línea.
- Overrides: `_get_domain` (quita el filtro de correlative y exige datos MF
  cuando `with_fiscal_machine`), `_get_domain_all_documents`, `search_moves`,
  `_get_sale_book_field_groups` (añade columnas N° Máquina Fiscal / Reporte Z /
  Serial), `_fields_sale_book_line`, y `parse_sale_book_data` +
  `_fields_sale_book_group_line` + `update_amounts` para el Resumen Diario.
- `wizards/accounting_reports_views.xml`: añade los dos checkboxes al wizard
  (heredando `l10n_ve_invoice.wizard_binaural_facturacion_reportes_view`),
  mutuamente excluyentes.
- `__manifest__.py`: registra la vista y sube versión 19.0.1.0.0 → 19.0.1.1.0.

## Capabilities

### New Capabilities
- `fiscal-machine-sale-book`: incluir en el Libro de Ventas los documentos de
  máquina fiscal (sin número de control), como Resumen Diario por Reporte Z o
  junto a los de forma libre.

## Impact

- Módulo: `l10n_ve_account_mf` (nuevo wizard extension + vista + manifest).
- No se toca `l10n_ve_invoice` (libro general por defecto igual), ni
  `l10n_ve_pos_mf`, ni el `invoice_print_type` de ninguna compañía.
- Sin las opciones marcadas, el libro se comporta exactamente igual que hoy.
- Las opciones aparecen también en el Libro de Compras (mismo wizard); para
  compras rinden resultados inocuos (las compras no tienen datos de máquina
  fiscal propia), igual que en V17.
- Verificación: manual en navegador (ver `tasks.md`); no se ejecutaron tests
  ni `odoo -u` como parte de este cambio.
- Referencia V17: `l10n_ve_iot_mf/wizards/accounting_reports.py`.
