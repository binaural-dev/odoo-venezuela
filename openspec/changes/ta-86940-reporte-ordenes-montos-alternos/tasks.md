## 1. Reporte

- [x] 1.1 Campos `foreign_currency_id`, `foreign_untaxed_total` y `foreign_total_billed`, y su
  cálculo en la vista SQL con la tasa del pedido o la de la venta original en un reembolso
  (`l10n_ve_pos/report/pos_order_report.py`)
- [x] 1.2 Etiquetas de las medidas con el nombre de la moneda alterna en pivot y gráfico
  (`l10n_ve_pos/report/pos_order_report.py`)
- [x] 1.3 Medidas en las vistas pivot y gráfico (`l10n_ve_pos/views/pos_order_report_views.xml`,
  `l10n_ve_pos/__manifest__.py`)
- [x] 1.4 Traducción de los campos y las etiquetas (`l10n_ve_pos/i18n/es_VE.po`)

## 2. Pruebas

- [x] 2.1 Venta: subtotal y total en $ a la tasa del pedido
  (`l10n_ve_pos/tests/test_pos_order_report.py`)
- [x] 2.2 Reembolso parcial a la misma tasa: resta y el neto queda en la mitad
- [x] 2.3 Reembolso total a otra tasa: resta a la tasa de la venta original y el neto en $ es 0
- [x] 2.4 Pedido sin tasa: aparece con 0 en $
- [x] 2.5 Etiquetas «Subtotal USD» y «Total USD» en pivot y gráfico

## 3. Spec

- [ ] 3.1 Al mergear, aplicar la spec de cambios sobre `openspec/specs/l10n_ve_pos/spec.md` y
  archivar el change
