Venezuela - Proyectos
=====================

Este addon está pensado para empezar con una vertical de proyectos para Binaural.

Características
---------------

Este módulo extiende el panel de rentabilidad de proyectos (``project_right_side_panel``)
para mostrar los montos en **dos monedas simultáneas**:

- **Moneda principal** (ej. Bolívares): en la primera línea de cada celda.
- **Moneda extranjera** (ej. USD): en la segunda línea, con fuente itálica y color muted.

Ambos montos usan el formateo nativo de Odoo (``formatCurrency``), lo que garantiza:
- Símbolo de moneda correcto.
- Posición del símbolo (antes o después) según ``res.currency.position``.
- Separadores de miles y decimales según la configuración regional del usuario.
- Cantidad de decimales según la precisión definida en cada moneda.

Dependencias
------------

- ``sale_project``
- ``project_purchase``
- ``l10n_ve_sale``
- ``l10n_ve_rate``
- ``l10n_ve_accountant``

Notas
-----

- Los montos foreign **no se recalculan** con ninguna tasa de cambio; se leen directamente de los campos ``foreign_subtotal``, ``foreign_balance`` y ``foreign_amount`` que ya existen en la base de datos.
- Criterio de la columna en divisa:
  - **Facturado / Billed** = lo realmente facturado, leído del ``foreign_balance`` de las líneas de factura vinculadas (las notas de crédito lo netean).
  - **Por facturar / To invoice / To bill** = pronóstico, prorrateado por cantidad desde el subtotal en divisa de la orden (``qty_to_invoice``), espejo de ``untaxed_amount_to_invoice`` / ``untaxed_amount_to_bill`` del core.
- Las líneas de factura se prorratean con su **propia distribución analítica**, no con la de la orden de compra.
- El redondeo y los separadores dependen 100% de la configuración de ``res.currency`` y del idioma del usuario; no hay lógica custom de formateo.
