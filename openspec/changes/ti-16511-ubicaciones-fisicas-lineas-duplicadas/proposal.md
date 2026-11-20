## Why

Validar una transferencia hacia la ubicación de Salida fallaba con `ValueError: Expected singleton: stock.picking.alter.location.line(…)` en `stock.picking.alter.location.action_move_to_output`. El registro de Ubicaciones Físicas del producto tenía **dos líneas para la misma ubicación** en *Otras Ubicaciones del Producto*, y los métodos que suman o restan cantidades buscan la línea con `filtered(lambda l: l.location_id.id == …)` y operan `available_qty -= qty` asumiendo un único resultado (ticket #16511, reportado en maxcam).

Nada impedía el duplicado:

- `stock.picking.alter.location.line` no tenía restricción de unicidad por `(stock_alter_location_id, location_id)`.
- `product.template._get_quants_for_alter_lines` arma **una línea por quant**, no por ubicación: un producto con varios quants en la misma ubicación (lotes, paquetes, propietarios) nacía con líneas repetidas.
- La one2many del formulario es editable y la lista permite importar (en clientes que la habilitan), sin ningún control.

El mismo patrón `filtered(...)` + aritmética está en `action_receive_quantity`, `action_deliver_from_output`, `action_internal_transfer`, `subtract_physical_quantity`, el wizard `move.alter.location.qtities.wizard` y `_sync_relocation_ledger`: un solo duplicado rompe cualquiera de esos flujos, incluida la validación de pickings.

## What Changes

- `stock.picking.alter.location.line`: restricción SQL `UNIQUE(stock_alter_location_id, location_id)`. Cualquier entrada (formulario, importación, código) que intente repetir una ubicación en el mismo registro recibe un error claro en lugar de dejar el dato corrupto.
- `product.template._get_quants_for_alter_lines`: agrupa los quants por ubicación y crea una sola línea por ubicación con la suma de `available_quantity`, redondeada con la unidad de medida del producto.
- Migración `pre-migrate` (19.0.1.0.13): fusiona los duplicados existentes antes de crear la restricción. Por cada `(stock_alter_location_id, location_id)` repetido conserva la línea de menor `id`, le asigna la **suma** de `available_qty` (actualizando `write_date`) y borra las demás junto con sus `ir_model_data`. Sumar es neutro: `pick_quantity`, `total_alter_quantity` y `total_quantity` ya sumaban las líneas repetidas, así que ningún total visible cambia. Si la tabla todavía no existe (bases con `l10n_ve_stock` anterior a 19.0.1.0.6, donde nació el modelo) no hace nada.
- Migración `post-migrate` (19.0.1.0.13): deja una nota en el chatter de cada registro fusionado, en el idioma del administrador, con la ubicación, las cantidades originales y la suma. El pre-migrate le pasa los grupos en una tabla temporal de la sesión.
- Los métodos que operan sobre una línea por ubicación no cambian: con la restricción el `filtered` devuelve como máximo un registro.

## Impact

- Specs afectadas: `l10n_ve_stock` (nuevos requisitos: una línea por ubicación en Otras Ubicaciones del Producto; líneas iniciales agrupadas por ubicación; fusión de duplicados existentes).
- Código: `l10n_ve_stock/models/stock_picking_alter_location_line.py`, `models/stock_picking_alter_location.py`, `models/product_template.py`, `migrations/19.0.1.0.13/pre-migrate.py` y `post-migrate.py`, `i18n/es_VE.po`. Versión del manifest 19.0.1.0.13.
- Datos: la migración modifica las líneas repetidas de las bases que las tengan. Deja trazas en el log (registro, ubicación, cantidades fusionadas) y una nota en el chatter de cada registro para auditar qué se tocó.
- Origen verificado en una copia local de Maxcam (datos al 27-10-2026): los 9 grupos duplicados los creó el usuario Binaural por lote el 04-09-2026, en dos transacciones, con ids consecutivos y en ubicaciones distintas a la física: el patrón de una sincronización que creaba una línea por quant.
- Fuera de alcance: el par de líneas del traceback de producción es posterior a esa copia y no se pudo inspeccionar; `_get_quants_for_alter_lines` filtra por plantilla y no por variante (comportamiento previo, ticket aparte); la restricción no es `DEFERRABLE`, así que intercambiar las ubicaciones de dos líneas en un mismo guardado falla.
