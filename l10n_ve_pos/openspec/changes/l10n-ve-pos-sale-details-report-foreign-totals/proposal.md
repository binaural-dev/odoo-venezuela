# Fix: reporte "Detalles de venta" del PdV (KeyError: 'name') y restauración de los totales en moneda foránea (l10n_ve_pos)

## Why

Al pedir "Detalles de venta" desde la sesión de PdV (icono de tuerca), el
reporte fallaba con `RPC_ERROR` / `KeyError: 'name'` al renderizar
`point_of_sale.pos_session_sales_details`, en la línea que hace
`category['name']`.

Causa raíz: el commit `501a54584` (nov 2025, tarea #59569) comentó
`"views/report_saledetails.xml"` en el manifiesto de `l10n_ve_pos` como
fix rápido para un error no relacionado (variantes de producto en Odoo
19), pero dejó activo `report/report_saledetails.py`, que sobreescribía
`get_sale_details()` por completo (sin `super()`) con la forma de dato
"plana" de una versión anterior (v17: `products` = lista plana de
productos).

Desde entonces la plantilla que realmente se renderiza es la nativa de
Odoo 19 (`point_of_sale.pos_session_sales_details`), que espera
`products` como lista de **categorías** (`{'name', 'products', 'qty',
'total'}`), más `products_info`, `refund_products`, `refund_info`,
`taxes_info`, `refund_taxes`, `discount_number`, `discount_amount`,
`invoiceList`, `payments_per_method`, `cash_rounding_total`, etc. — nada
de eso lo devolvía el override de `l10n_ve_pos`, de ahí el `KeyError`.
El bug llevaba 9 meses latente porque nadie había vuelto a imprimir este
reporte desde el fix de nov 2025 hasta ahora (sesión de hoy,
2026-07-31, BD `pos` del contenedor `proj`).

Además, el override viejo era el único lugar donde se mostraba el total
pagado en moneda foránea (Bs/USD) de la sesión — funcionalidad relevante
para la localización VZ (ver `openspec/migration-lessons.md`, sección
sobre consumidores de `foreign_amount`). Al arreglar el crash, se
aprovecha para restaurar esa información pero como una **extensión**
sobre la plantilla nativa (no un reemplazo total), para no perder todo lo
que Odoo 19 agregó al reporte (reembolsos, descuentos, arqueo de caja,
facturas).

## What Changes

- `report/report_saledetails.py`: `get_sale_details()` ahora llama a
  `super()` y usa la estructura nativa de Odoo 19 tal cual. Encima,
  agrega:
  - `foreign_currency`: `res.currency` foránea de la compañía
    (`company.foreign_currency_id`), o vacío si no está configurada.
  - `foreign_total_paid`: suma de `pos.payment.foreign_amount` de todos
    los pagos del período/sesión(es) consultados.
  - `payments[]`: cada pago nativo gana `f_total` (su equivalente
    foráneo), agrupado por método de pago + sesión vía SQL directo sobre
    `pos_payment`/`pos_payment_method`.
  - `payments_per_method`: recalculado para incluir también `f_total`
    acumulado por método (antes solo tenía `total`).
- `views/report_saledetails.xml`: en vez de reemplazar por completo el
  `t-call` a `point_of_sale.pos_session_sales_details` (como hacía antes
  de nov 2025), ahora hereda esa plantilla nativa vía `inherit_id` y solo
  inserta 3 columnas nuevas (con `t-if="foreign_currency"`, para no
  romper nada si la compañía no tiene moneda foránea configurada):
  monto foráneo por pago, total foráneo de la sesión, y monto foráneo por
  método de pago agrupado.
- `__manifest__.py`: se descomenta `"views/report_saledetails.xml"` en
  `data` y se sube versión `1.7` → `1.8` (requiere `-u l10n_ve_pos` para
  cargar la vista en base de datos).

## Impact

- **Capability**: `pos-sale-details-foreign-totals` (nueva).
- **Módulo**: `l10n_ve_pos`, backend (`report/report_saledetails.py`) y
  vista QWeb (`views/report_saledetails.xml`). Requiere `-u l10n_ve_pos`
  para que la vista quede registrada (el método Python ya se recarga
  solo, pero la vista QWeb no existía en absoluto en la BD hasta este
  cambio).
- Compañías sin `foreign_currency_id` configurado: sin cambio visible,
  las columnas nuevas no se renderizan (`t-if="foreign_currency"`).
- Este mismo archivo está duplicado (repos independientes) en
  `custom/2doce-market`, `custom/megasoft-2doce` y
  `custom/19-homologacion-jul-2026-pos` — **no** se tocan en este change;
  si esos proyectos necesitan el mismo fix, es un change aparte por
  repo.
- No se corrieron tests ni `-u` de verificación en este pase (se deja
  para que el usuario lo pruebe en el navegador tras el upgrade del
  módulo).
