# Feature: modo Kiosko "solo escaneo / búsqueda" con saludo al cliente

## Why

En algunos despliegues del Kiosko no se quiere exponer el catálogo completo de
productos (categorías + grilla): el cliente debe añadir productos únicamente
**escaneando** el código de barras o **buscando** por nombre/código. El modo
nativo de `pos_self_order` siempre pinta el catálogo y no ofrece buscador de
texto (solo hay escaneo por lector, ya cableado globalmente en
`self_order_service`). Se necesita, de forma opcional por punto de venta:

1. Ocultar el catálogo en modo Kiosko.
2. Añadir un **buscador** de texto (nombre / código de barras / referencia).
3. Mostrar arriba un **saludo personalizado** ("¡Hola {nombre}!") usando el
   contacto ya identificado por cédula al inicio del Kiosko.

Alcance: página de lista de productos del modo **Kiosko**. Es aditivo y
opcional (ajuste por caja); no altera el flujo QR/móvil ni el escaneo nativo.

## What Changes

- **Ajuste nuevo por punto de venta** `pos.config.self_ordering_hide_catalog`
  (booleano), expuesto en Ajustes → sección de Autopedido/Kiosko, visible solo
  cuando el modo es `kiosk`. Se envía al frontend vía
  `_load_pos_self_data_fields`.

- **Frontend** (`ProductListPage`, patch + plantilla heredada + scss), activo
  solo cuando `self_ordering_mode === "kiosk"` y `self_ordering_hide_catalog`:
  - Oculta la barra de categorías, la de subcategorías y la grilla del catálogo.
  - Inserta arriba un **saludo** "¡Hola {nombre del contacto}!" a partir de
    `currentOrder.partner_id.name` (con fallback "¡Hola!" si no hubiera nombre).
  - Inserta un **buscador**: `input` que filtra `product.template` disponibles
    (`self_order_available`) por nombre / `display_name` / `barcode` /
    `default_code`, con tope de 50 resultados. Los resultados se pintan con las
    **mismas tarjetas** del catálogo (reutilizando `productCategories`/
    `getProducts`/`selectProduct`), de modo que tocar un resultado añade al
    carrito exactamente igual que el catálogo (incluye combos/configurables).
  - Guarda los helpers de la barra de categorías (`ensureCategoryVisible`,
    `toggleSubCategoryPanel`, `getSubCategories`) para no romper el render al
    quitar sus nodos del DOM.
  - **Resumen del pedido en-sitio**: cuando el catálogo está oculto y no hay
    búsqueda activa, el área central muestra las líneas del pedido actual
    (imagen, nombre, cantidad con `−`/`+`, precio y eliminar), actualizándose en
    vivo al escanear/añadir. Reutiliza las utilidades del carrito
    (`getDisplayPriceWithQty`, `removeLine`, `formatProductName`). Si hay
    búsqueda activa, se muestra en su lugar la grilla de resultados.
  - **Escaneo por lector**: sigue funcionando (listener global de
    `self_order_service`) pero **ya no salta al carrito** en este modo; el
    cliente permanece en la pantalla y el producto aparece en el resumen. Se
    logra con un patch de `SelfOrderRouter.navigate` que traga la navegación
    automática a `cart` mientras `suppressScanCartNav` está activo (lo activa
    `ProductListPage` mientras la pantalla está montada); la navegación
    explícita (`review`/botón de pago) la deja pasar vía `_allowScanCartNav`.

- **i18n**: nuevas cadenas fuente en inglés dentro de `_t()` con su traducción
  `es_VE` ("¡Hola %(name)s!", "Busca o escanea un producto…", etc.). El módulo
  ya está registrado en `_get_translation_frontend_modules_name`.

## Capabilities

### Added Capabilities

- `pos-self-order-kiosk-scan-search`: modo opcional del Kiosko que oculta el
  catálogo y deja solo escaneo + buscador de texto, con saludo personalizado al
  cliente identificado.

## Impact

- **Módulo**: `l10n_ve_pos_self_order`.
  - Backend: `models/pos_config.py`, `models/res_config_settings.py`,
    `views/res_config_settings_views.xml` (herencia de la vista de ajustes de
    `pos_self_order`).
  - Frontend: `static/src/overrides/product_list_page.{js,xml,scss}` y
    `static/src/overrides/self_order_router_service.js` (bundle
    `pos_self_order.assets`).
  - i18n: `i18n/es_VE.po`.
- **No toca** controladores, RPC ni el flujo de identificación.
- **Compatibilidad**: con el ajuste desactivado, el comportamiento del Kiosko es
  idéntico al nativo (catálogo visible, sin saludo ni buscador).
- **Nota de hardware/UX**: el buscador es un `<input>` de texto. En un Kiosko
  táctil sin teclado físico depende de que el terminal muestre teclado en
  pantalla al enfocar el campo (`inputmode="search"`). Si el hardware no lo
  hace, habría que añadir un teclado QWERTY en pantalla (fuera de este alcance).
- **Riesgo**: bajo. Aditivo y detrás de un flag; el escaneo nativo no cambia.

References: Kiosko / Autopedido POS V19 (`pos_self_order`).
