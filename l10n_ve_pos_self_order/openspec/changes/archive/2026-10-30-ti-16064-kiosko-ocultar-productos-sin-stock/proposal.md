# Fix: "Mostrar solamente los productos disponibles" también en el Kiosko (ti 16064)

## Why

El ticket 16064 pide que, con "Mostrar solamente los productos disponibles"
(`res.company.pos_show_just_products_with_available_qty`), el PdV no muestre
los productos almacenables sin cantidad disponible. En `l10n_ve_pos` la caja
ya los oculta (`ProductTemplate.canBeDisplayed` con el `qty_available` de la
ubicación de origen de la caja), pero el Kiosko no:

- El Kiosko no pasa por `canBeDisplayed`: arma la cuadrícula
  (`self_order_service.initProducts`), el buscador del modo "solo escaneo /
  búsqueda" y el escaneo con todas las plantillas que carga.
- Su carga (`/pos-self/data/<caja>`, `pos.config.load_self_data`) lee las
  variantes con el `read` genérico, sin el contexto de ubicación que
  `l10n_ve_pos` pone en `product.product._load_pos_data_read`.
- Las opciones de los combos las agrega el core con una segunda lectura por id
  que no pasa por el dominio de carga.

En `pos_consultor`, con el ajuste activo, el Kiosko seguía ofreciendo "Opcion
5" (-1), "Producto Exento" (-13) y "Prueba 15684 Lampara" (-3).

## What Changes

- `models/product_template.py`:
  - `_load_pos_self_data_domain` deja fuera de la carga los almacenables sin
    ninguna variante con `qty_available` positiva en la ubicación de origen
    del tipo de operación de la caja y sus hijas (la misma cantidad de la caja
    y de "Cantidad en 0"). Mismo mecanismo que el core con
    `self_order_available`. Las variantes siguen a sus plantillas.
  - `_load_pos_self_data_read` manda con `self_order_available = False` las
    almacenables sin stock que el core agrega como opción de un combo. El core
    no deja elegirlas en el combo ("Agotado") y responde "no disponible" al
    escanearlas; el buscador de "solo escaneo / búsqueda" ya las salta.
- `static/src/overrides/self_order_service.js` y `pos_category.js`: con el
  ajuste, la cuadrícula no muestra los almacenables con
  `self_order_available = False`, que el core pintaría como tarjeta "Agotado":
  `PosCategory.associatedProducts` para las categorías reales (y sus pestañas)
  e `initProducts` para "Sin categoría".
- `models/pos_config.py`: el ajuste se manda al frontend del autopedido.
- Lo no almacenable (servicios, consumibles sin control de stock, combos) se
  sigue cargando. Con el ajuste apagado la carga es la nativa. Aplica a todos
  los modos de autopedido (Kiosko y móvil).
- El Kiosko no guarda caché en el navegador: cada carga de la página lee el
  stock actual; no hace falta el refresco que `l10n_ve_pos` fuerza en la caja.

## Capabilities

### Added Capabilities

- `pos-self-order-kiosk-available-products`: el autopedido no ofrece
  almacenables sin stock en la ubicación de origen cuando la compañía activa
  "Mostrar solamente los productos disponibles".

## Impact

- **Módulo**: `l10n_ve_pos_self_order` (`models/product_template.py`,
  `models/pos_config.py`, `static/src/overrides/self_order_service.js`,
  `static/src/overrides/pos_category.js` y sus tests). Versión `19.0.1.5.0` → `19.0.1.6.0`.
- **Tope de carga**: `point_of_sale.limited_product_count` cuenta solo
  productos que se pueden vender.
- **Límites con la página abierta** (en la spec): el filtro no se recalcula
  hasta recargar la página o abrir la sesión.
- **Combos que no se pueden completar** (en la spec): un combo cuya única
  opción de un grupo no tiene stock se ofrece, pero el core lo quita al pagar.
- **Fuera de alcance**: elegir una variante sin stock de un producto con
  alguna variante con stock (igual que la caja) y ocultar los combos que no se
  pueden completar.
