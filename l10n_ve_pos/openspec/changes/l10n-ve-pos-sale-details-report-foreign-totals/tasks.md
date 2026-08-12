# Tasks

## 1. Diagnóstico

- [x] 1.1 Reproducir el `KeyError: 'name'` a partir del traceback RPC y
      ubicar la plantilla real que falla (`point_of_sale.pos_session_sales_details`,
      no la de `l10n_ve_pos`)
- [x] 1.2 Confirmar en BD (`pos`, contenedor `proj`) que no existe ninguna
      `ir.ui.view` con `key='l10n_ve_pos.report_saledetails'` — la vista
      nunca llegó a cargarse
- [x] 1.3 `git log`/`git blame` sobre `__manifest__.py` → commit
      `501a54584` (nov 2025, tarea #59569) comentó la vista como fix de
      un problema no relacionado, sin tocar el método Python
- [x] 1.4 Confirmar que `report/report_saledetails.py` seguía activo
      (los `.py` se cargan independientemente de `data` en el manifiesto)
      y que su forma de retorno (`products` plano) no calza con lo que
      pide la plantilla nativa de Odoo 19

## 2. Implementación

- [x] 2.1 `report/report_saledetails.py`: `get_sale_details()` delega en
      `super()` y agrega `foreign_currency`, `foreign_total_paid`,
      `payments[].f_total`, `payments_per_method[].f_total`
- [x] 2.2 `views/report_saledetails.xml`: reescrito como `inherit_id` de
      `point_of_sale.pos_session_sales_details` (antes reemplazaba
      `point_of_sale.report_saledetails` completo) con 3 xpath aditivos,
      todos gateados por `t-if="foreign_currency"`
- [x] 2.3 `__manifest__.py`: descomentar la vista en `data`, subir
      versión 1.7 → 1.8
- [x] 2.4 Validar sintaxis Python (`compile()`) y XML (`lxml`), y
      verificar que los 3 `expr` de xpath matchean exactamente 1
      elemento contra la plantilla nativa de Odoo 19

## 3. Pendiente (a cargo del usuario)

- [ ] 3.1 `-u l10n_ve_pos` en el contenedor `proj` (u otro ambiente) para
      registrar la vista nueva en BD
- [ ] 3.2 Probar en el navegador: "Detalles de venta" desde una sesión de
      PdV, con y sin `foreign_currency_id` configurado en la compañía
- [ ] 3.3 Evaluar si el mismo fix debe replicarse en
      `custom/2doce-market`, `custom/megasoft-2doce` y
      `custom/19-homologacion-jul-2026-pos` (repos independientes, no
      tocados en este change)

## 4. OpenSpec

- [x] 4.1 `openspec change validate l10n-ve-pos-sale-details-report-foreign-totals` → válido
