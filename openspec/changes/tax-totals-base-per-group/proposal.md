## Why

En una factura cuya moneda difiere de la de la compañía (ej. USD, compañía en VEF) con dos o más grupos de IVA distintos (ej. 0%/exento y 16%), el widget de totales y el PDF (`account.move.tax_totals`) muestran un `base_amount` (VEF) por grupo que no coincide con el `balance` realmente posteado en `account.move.line` — confirmado en una factura de proveedor real: el widget mostraba Bs. 217.994,27 para el grupo 16% mientras la línea real posteó Bs. 217.994,28. El total agregado de la factura sí cuadra; el desfase vive en el reparto entre grupos. (Ticket #15412.)

Causa: `AccountTax._fix_base_amount_for_multi_currency` (introducido junto al fix de `round_per_line`, PR #1362) corrige bien el `base_amount` TOTAL sumando el `balance` real de todas las líneas de producto, pero para bajar esa corrección a cada `tax_group` individual reparte el diferencial por PROPORCIÓN (usando los montos naive del core como ratio) en vez de volver a sumar el `balance` real de las líneas que pertenecen a CADA grupo específico. Eso solo garantiza que el total cuadre, no que cada grupo lo haga.

## What Changes

- `l10n_ve_accountant`: en `AccountTax._fix_base_amount_for_multi_currency`, reemplazar el reparto proporcional de `base_amount` entre `tax_groups` por el recalculo directo desde el `balance` real de las líneas de producto que pagan cada impuesto (vía `involved_tax_ids`, con fallback a `children_tax_ids` para un tax tipo 'group' cuyos hijos comparten la misma base). El último grupo de cada subtotal sigue tomando el remanente exacto para garantizar que la suma cuadre; el reparto proporcional queda solo como respaldo defensivo si no se pueden identificar las líneas propias de un grupo.
- Bump de manifest `l10n_ve_accountant` 19.0.1.0.22 → 19.0.1.0.23.

## Impact

- Specs afectadas: `l10n_ve_accountant` (nueva requirement "base_amount por grupo de impuesto coincide con el balance real").
- Código: `l10n_ve_accountant/models/account_tax.py` (`_fix_base_amount_for_multi_currency`).
- Solo afecta el `base_amount` por `tax_group` que reporta el widget/PDF de facturas multimoneda con 2+ grupos de impuesto distintos. No cambia el total agregado (ya estaba correcto), ni el `tax_amount` (ya corregido por `_fix_tax_amount_for_round_per_line`), ni la partida doble contable.
