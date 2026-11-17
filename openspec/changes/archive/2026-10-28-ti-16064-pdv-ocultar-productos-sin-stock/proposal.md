## Why

Ticket https://www.binauraldev.com/odoo/helpdesk/58/tickets/16064 (referencia #16102): se pide
que, con una configuración, el PdV muestre solo los productos que tienen cantidad disponible. Un
producto disponible en el PdV pero sin stock no debe salir en la pantalla. Si la configuración
está apagada, el bloqueo de vender sin stock ya lo hace "Cantidad en 0" (`amount_to_zero`).

La configuración ya existe en `l10n_ve_pos`: "Mostrar solamente los productos disponibles"
(`res.company.pos_show_just_products_with_available_qty`). Pero en O19 no hace nada, por dos
fallos de la migración:

- El filtro de O17 quedó como un getter `productsToDisplay` parcheado en `ProductScreen`. En O19
  ese getter vive en `PosStore` y la plantilla lee `pos.productsToDisplay`/`pos.productToDisplayByCateg`,
  así que el parche nunca se ejecuta. Además deja pasar todo lo de tipo `consu`, que en O19
  incluye los almacenables (`is_storable`).
- El loader de `product.product` pasa el almacén de la caja con la clave `warehouse` de O17. El
  módulo `stock` de O19 lee `warehouse_id`, así que `qty_available` y `free_qty` llegan al PdV
  sumando todos los almacenes de la compañía (en `pos_consultor`, "Caja Lara" recibía 781
  unidades de "Producto IVA 16" sin tener ninguna en su almacén).

## What Changes

- `ProductTemplate.canBeDisplayed` (frontend, nuevo parche en
  `static/src/overrides/models/product_template.js`): con el ajuste activo, un producto
  almacenable sin ninguna variante con `qty_available` positiva no se muestra. En O19 es lo único
  que consulta `PosStore.filterExcludedProducts`, el filtro de la cuadrícula (con o sin agrupar
  por categoría) y de la búsqueda; además va antes del tope de 100 productos de ese filtro, así
  que los ocultos no le quitan lugar a los que sí tienen stock.
- Se compara contra el stock **a mano** (`qty_available`), igual que O17 y que "Cantidad en 0":
  lo reservado por otras órdenes no lo oculta.
- Lo no almacenable (servicios, consumibles sin control de stock, combos) se sigue mostrando.
- Se elimina el getter muerto `productsToDisplay` del parche de `ProductScreen`.
- `product.product._load_pos_data_read` pasa `location=<ubicación de origen>` en el contexto: la
  cantidad que llega al PdV es la de la ubicación de origen del tipo de operación de la caja (y sus
  hijas), la misma que valida "Cantidad en 0" (`pos.config.check_stock_availability`). Con todo el
  almacén, una caja que vende desde una ubicación fuera de él ("Caja Operativa" en `pos_consultor`
  vende desde "Estante 1", fuera de OPER) ocultaría lo que sí puede vender, y el stock de otra
  ubicación del almacén mostraría lo que "Cantidad en 0" bloquea. No se pasa también
  `warehouse_id`: `stock` intersecta ambas claves. La ubicación de origen es obligatoria en el
  tipo de operación, así que no hace falta respaldo por almacén.
- Con el ajuste activo, `pos.session.load_data` marca el contexto `pos_reload_stock_dependent_data`
  y `pos.load.mixin._last_server_date_to_load` quita el filtro por `write_date` de
  `product.template` y `product.product`: al abrir una sesión nueva o entrar desde el backend la
  caja recibe las variantes con el stock actual, no solo las modificadas desde su caché. Un
  movimiento de stock no cambia el `write_date` del producto, así que sin esto un producto
  repuesto seguía oculto (y uno agotado, visible) hasta "Volver a cargar datos". Es el mismo
  patrón de `binaural_pos_multicurrency` para la tasa en las cajas en otra moneda.
- La ayuda del ajuste ("Deletes automatically products without free qty on POS", sin traducir)
  pasa a "Oculta los productos almacenables sin stock a mano en la ubicación de origen de la
  caja".

## Impact

- **Módulo tocado:** `l10n_ve_pos` (19.0.1.26.0 → 19.0.1.27.0).
- **Despliegue:** `-u l10n_ve_pos` (cambia la ayuda del ajuste y su traducción). Sin cambio de
  esquema. Con el ajuste activo, la primera vez que se abre cada caja (sesión nueva o desde el
  backend) recibe la cantidad de su ubicación de origen; una caja que ya está abierta en el navegador
  necesita "Volver a cargar datos" → "Limitado".
- **Costo:** con el ajuste activo, cada apertura carga los productos como la primera vez (hasta
  `point_of_sale.limited_product_count` plantillas, 5000 por defecto), no solo los modificados.
- **Refresco del stock con la sesión abierta (recomendación):** F5 con la sesión abierta no
  consulta al servidor: la caja sigue con la cantidad que tiene cargada. Para tomar el stock
  actual sin cambiar de sesión se usa "Volver a cargar datos" → "Limitado": vacía IndexedDB igual
  que "Completo" y recarga hasta `point_of_sale.limited_product_count` plantillas; las que quedan
  fuera llegan con su stock actual al buscarlas. Como cualquier recarga del PdV, descarta las
  órdenes sin guardar (sincroniza antes y no sigue si hay una orden pagada sin sincronizar).
- **Efecto en otros módulos:** cualquier JS que lea `qty_available`/`free_qty` de
  `product.product` en el PdV pasa a ver la cantidad de la ubicación de origen de la caja (antes,
  por la clave ignorada, la de todos los almacenes).
- **Fuera de alcance:** refrescar el stock con F5 o durante la sesión sin recargar los datos: al
  vender la última unidad el producto sigue visible hasta la próxima carga ("Cantidad en 0"
  bloquea el pago). El escaneo de código de barras no pasa por este filtro.
