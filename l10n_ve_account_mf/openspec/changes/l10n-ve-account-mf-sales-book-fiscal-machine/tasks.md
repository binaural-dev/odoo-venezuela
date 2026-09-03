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
