## 1. Extensión del wizard

- [x] 1.1 `wizards/accounting_reports.py`: heredar `wizard.accounting.reports`,
      campos `with_fiscal_machine` y `all_documents`
- [x] 1.2 Overrides de dominio: `_get_domain`, `_get_domain_all_documents`,
      `_fiscal_machine_domain`
- [x] 1.3 Override `search_moves` (rama all_documents = unión; rama
      with_fiscal_machine = orden por fecha/número MF)
- [x] 1.4 Columnas MF en `_get_sale_book_field_groups` +
      `_fields_sale_book_line`
- [x] 1.5 Resumen Diario: `parse_sale_book_data`, `_fields_sale_book_group_line`,
      `update_amounts`
- [x] 1.6 `wizards/accounting_reports_views.xml`: dos checkboxes en el wizard
- [x] 1.7 Registrar en `wizards/__init__.py` y `__manifest__.py` (data + bump
      versión 19.0.1.1.0)
- [x] 1.8 Columnas del modo "Con máquina fiscal" replican el layout de V17
      (`_fiscal_machine_sale_book_groups`); "Incluir todos los documentos"
      mantiene el layout V19

## 2. Verificación funcional (manual, en navegador)

- [ ] 2.1 Actualizar el módulo `l10n_ve_account_mf`
- [ ] 2.2 Contabilidad → Reportes → Libro de Ventas: deben aparecer los campos
      "Con máquina fiscal" e "Incluir todos los documentos emitidos"
      (excluyentes entre sí)
- [ ] 2.3 Marcar "Con máquina fiscal", rango con ventas fiscales del PdV
      (Reporte Z impreso): el xlsx trae el Resumen Diario agrupado por Reporte
      Z, con columnas N° Máquina Fiscal / Reporte Z / Serial
- [ ] 2.4 Marcar "Incluir todos los documentos emitidos": el xlsx trae forma
      libre (con número de control) + máquina fiscal (sin número de control),
      línea por línea
- [ ] 2.5 Sin marcar nada: el libro sale idéntico a hoy (solo documentos con
      número de control)
- [ ] 2.6 Comprobar que los totales del resumen del pie cuadran con las líneas

## 3. Correcciones de la revisión (PR #1270)

- [x] 3.1 `search_moves` (modo MF): re-filtrar a solo documentos de máquina
      fiscal tras `super()` (`_only_fiscal_machine`), porque otros módulos
      inyectan asientos ignorando el dominio (retenciones de payment_extension)
- [x] 3.2 `search_moves` (modo todos): partir de `super().search_moves()` y unir
      la búsqueda de MF, en vez de reemplazar la búsqueda entera
- [x] 3.3 Resumen Diario: reescribir `parse_sale_book_data` con `flush` explícito
      → elimina el doble conteo, cierra el resumen antes de cada nota de débito y
      al final del Reporte Z, y sustituye el proxy por monto por una bandera
- [x] 3.4 Agrupar el Resumen por `invoice_date_display` (no `create_date`, UTC)
- [x] 3.5 Ocultar los checkboxes en el Libro de Compras (`report == 'purchase'`)
- [x] 3.6 `_logger.warning` cuando no se encuentra el punto de inserción de las
      columnas de MF
- [x] 3.7 Documentar la incompatibilidad con `l10n_ve_iot_mf` (`proposal.md`)
- [x] 3.8 Corregir `spec.md` (columnas del modo MF) y subir versión a 19.0.1.2.0

## 4. Segunda revisión (PR #1270, 2026-09-15)

- [x] 4.1 (A) Añadir `l10n_ve_tax_payer` al `depends` del manifest — el Resumen
      usa `partner_id.taxpayer_type`, que solo define ese módulo y no llega por
      el cierre transitivo de las demás dependencias
- [x] 4.2 (B) Gatear el modo MF por `report == "sale"` (`_mf_mode()`): la casilla
      queda oculta en Compras pero su valor no se limpiaba, y el libro de compras
      salía vacío exigiendo datos de MF
- [x] 4.3 Eliminar `_get_domain_all_documents` (el `_domain_free_form` quedaba sin
      usar); el dominio de MF se calcula en `search_moves`. Versión → 19.0.1.2.1
- [ ] 4.4 Validación funcional del modo MF sobre `2doce212` con ESTE commit, con y
      sin Sucursal, y pegar el cuadre líneas vs pie (task 2.6) → cierra [15]
