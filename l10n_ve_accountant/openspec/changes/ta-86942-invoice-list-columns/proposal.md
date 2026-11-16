# Mejora visual: columnas de montos en las listas de facturas y notas

Tarea: https://www.binauraldev.com/odoo/action-341/86942

## Why

En Contabilidad › Clientes › Facturas (y en notas de crédito de clientes y de
proveedores, y facturas de proveedores) las columnas de montos tenían tres
problemas:

- No todas totalizaban al pie de la lista: `Total Bs.` y `Total USD` sí, pero
  `amount_untaxed_signed` y `amount_total_signed` (Bs.) y `foreign_untaxed_total`
  y `foreign_total_billed` ($) no tenían `sum`.
- El orden mezclaba monedas: los Bs. y los $ aparecían intercalados.
- Sin ancho predeterminado: los números largos se cortaban con puntos
  suspensivos (`1.171.227,35...`) y cada usuario tenía que ajustar el ancho al
  entrar.

## What Changes

`l10n_ve_accountant_view_invoice_tree_inherit` (`views/account_move.xml`, hereda
`account.view_invoice_tree`, de la que cuelgan las cuatro listas):

- Las seis columnas de montos van contiguas y en este orden: Bs. sin impuestos,
  Bs. impuesto, Bs. total, $ sin impuestos, $ impuesto, $ total. El impuesto va
  siempre después del total sin impuestos, en ambas monedas.
- Todas llevan `sum="Total"` y `optional="show"`.
- Campo nuevo `foreign_tax_total` (almacenado, calculado como
  `foreign_total_billed - foreign_untaxed_total`) para poder mostrar y
  totalizar el impuesto en moneda alterna. El impuesto en Bs. reutiliza
  `amount_tax_signed`, movido a su nueva posición.
- Ancho predeterminado: `width="180px"` en las columnas de montos (las seis
  propias, `Impuestos no incluidos`, `Total` e `Importe adeudado`)
  y `140px` en `Número`.

Se mantiene el atributo nativo `width` en lugar de una clase CSS: la lista de
Odoo usa `table-layout: fixed` con anchos en línea, y una clase no evita el
recorte con puntos suspensivos.

## Capabilities

### New Capabilities
- `invoice-list-amount-columns`: las listas de facturas y notas muestran los
  montos agrupados por moneda, totalizados al pie y con ancho predeterminado.

## Impact

- Archivos: `l10n_ve_accountant/views/account_move.xml`,
  `models/account_move.py` (campo `foreign_tax_total` y etiquetas),
  `i18n/es_VE.po`, `__manifest__.py` (versión `.45`), `tests/test_invoice_list_columns.py`, `tests/__init__.py`.
- Campo almacenado nuevo: al actualizar el módulo Odoo lo calcula para las
  facturas existentes, sin migración.
- Usuarios que ya ajustaron columnas conservan sus anchos guardados en el
  navegador hasta restablecerlos.
