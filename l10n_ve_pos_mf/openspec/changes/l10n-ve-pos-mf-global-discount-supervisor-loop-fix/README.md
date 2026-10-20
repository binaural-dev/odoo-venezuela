# l10n-ve-pos-mf-global-discount-supervisor-loop-fix

Corrige un bucle infinito de popups de supervisor (pantalla negra / caja
congelada) al aplicar el descuento global cuando la caja exige clave de
supervisor para eliminar líneas: la conversión Estrategia A elimina sus
propias líneas de descuento con `line.delete()` (síncrono, sin gate) en vez
de `order.removeOrderline()` (async y gateado por `binaural_pos_hr`).
