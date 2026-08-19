# Tasks

## 1. Ajuste por punto de venta

- [x] 1.1 `models/pos_config.py`: campo `self_ordering_hide_catalog` (Boolean) y
      override de `_load_pos_self_data_fields` para exponerlo al frontend
- [x] 1.2 `models/res_config_settings.py`: related `pos_self_ordering_hide_catalog`
- [x] 1.3 `views/res_config_settings_views.xml`: `<setting>` en la sección de
      Autopedido/Kiosko, visible solo cuando `pos_self_ordering_mode == 'kiosk'`
- [x] 1.4 `__manifest__.py` + `models/__init__.py`: registrar vista y modelos

## 2. Frontend — ocultar catálogo + buscador + saludo

- [x] 2.1 `product_list_page.js` (patch): getter `hideCatalog`
      (kiosk + flag), `greeting` (partner), `searchState`, `searchResults`
      (filtro por nombre/barcode/ref, tope 50)
- [x] 2.2 `product_list_page.js`: override de `productCategories`/`getProducts`
      para alimentar la grilla con los resultados de búsqueda; `selectProduct`
      limpia la búsqueda tras añadir
- [x] 2.3 `product_list_page.js`: guardas en `ensureCategoryVisible`,
      `toggleSubCategoryPanel`, `getSubCategories` cuando `hideCatalog`
- [x] 2.4 `product_list_page.xml` (t-inherit): saludo + buscador arriba; ocultar
      barras de categoría/subcategoría; hints de "escanea/busca" y "sin resultados"
- [x] 2.5 `product_list_page.scss`: estilos del header (saludo grande + input)

## 2b. Resumen del pedido en-sitio + retener escaneo

- [x] 2b.1 `product_list_page.js`: `orderLines`, `showOrderSummary`,
      `getLinePrice`, `changeLineQuantity`, `removeSummaryLine`,
      `formatProductName`
- [x] 2b.2 `product_list_page.xml`: bloque de resumen (imagen, nombre, `−`/`+`,
      precio, eliminar); prioridad búsqueda > resumen > pista
- [x] 2b.3 `self_order_router_service.js`: patch de `navigate` que traga la
      navegación a `cart` del escaneo (`suppressScanCartNav`) y deja pasar la
      explícita (`_allowScanCartNav`); `ProductListPage` activa/desactiva el flag
- [x] 2b.4 `product_list_page.scss`: estilo del título del resumen
- [x] 2b.5 `product_list_page.js`: `review()` en modo hideCatalog llama a
      `payDirectly()` (mirror de `CartPage.pay()` sin ramas móvil/mesa) → salta
      el carrito y va a métodos de pago; fallback al carrito si faltan datos

## 3. i18n

- [x] 3.1 `i18n/es_VE.po`: cadenas nuevas (saludo, placeholder, hints, ajustes)

## 4. Verificación manual (navegador) — PENDIENTE

- [ ] 4.1 Upgrade del módulo y activar el ajuste en un PdV en modo Kiosko
- [ ] 4.2 Identificarse por cédula → ver "¡Hola {nombre}!" arriba, sin catálogo
- [ ] 4.3 Escanear un producto con lector → se añade y **aparece en el resumen
      en-sitio sin saltar al carrito**
- [ ] 4.4 Buscar por nombre/código → resultados en tarjetas; tocar añade y
      aparece en el resumen; combos/configurables navegan correctamente
- [ ] 4.5 Editar cantidades / eliminar desde el resumen; totales OK
- [ ] 4.6 Botón de pago → **salta directo a métodos de pago** (sin carrito)
- [ ] 4.7 Desactivar el ajuste → el Kiosko vuelve al catálogo nativo idéntico
      (el escaneo vuelve a saltar al carrito)

## 5. OpenSpec

- [ ] 5.1 `openspec change validate kiosk-scan-search-only --strict` → válido
