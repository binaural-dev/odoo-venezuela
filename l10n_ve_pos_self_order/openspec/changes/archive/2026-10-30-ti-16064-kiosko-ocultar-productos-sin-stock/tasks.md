# Tasks

## 1. Carga del autopedido

- [x] 1.1 `models/product_template.py`: `_load_pos_self_data_domain` excluye los
      almacenables sin variante con `qty_available > 0` en la ubicación de
      origen (`location=`) cuando la caja tiene el ajuste
- [x] 1.2 `models/product_template.py`: `_load_pos_self_data_read` manda con
      `self_order_available = False` las opciones de combo almacenables sin
      stock
- [x] 1.3 `models/pos_config.py`: `pos_show_just_products_with_available_qty`
      en `_load_pos_self_data_fields`
- [x] 1.4 `models/__init__.py`, `__manifest__.py` (`19.0.1.6.0`)

## 2. Cuadrícula

- [x] 2.1 `static/src/overrides/pos_category.js`: con el ajuste,
      `PosCategory.associatedProducts` (categorías reales y sus pestañas) no
      devuelve los almacenables con `self_order_available = false`
- [x] 2.2 `static/src/overrides/self_order_service.js`: mismo filtro en
      `initProducts` para "Sin categoría"

## 3. Pruebas

- [x] 3.1 `tests/test_kiosk_product_available_qty.py`: 11 casos (sin stock,
      no almacenables, stock en una hija de la ubicación de origen, otro
      almacén, stock negativo, una variante con stock, ajuste apagado, opción
      de combo sin stock / con stock / con el ajuste apagado, carga por
      `load_self_data` con el privilegio reducido de la ruta pública)
- [x] 3.2 `static/tests/unit/self_order_available_qty.test.js`: 3 casos
      (categoría real, "Sin categoría", ajuste apagado)
- [x] 3.3 Mutaciones: sin el filtro de carga fallan los 4 casos que dependen de
      él; sin marcar las opciones de combo falla el caso del combo; sin
      filtrar `associatedProducts` falla el Hoot de la categoría real
- [x] 3.4 Suite del módulo: los tests de facturas y de `recompute_prices` usan la
      tasa del día (`l10n_ve_rate` solo acepta la fecha exacta) y no dependen
      de las tasas ni de los RIF de la base (commit `[TEST]` aparte)

## 4. Evidencia (2026-10-30)

Submódulos de la instancia `pos` al día con `19.0` y `-u` de los módulos
cambiados.

- `pos_consultor`: `--test-tags /l10n_ve_pos_self_order,/l10n_ve_pos:TestPosProductAvailableQty,/l10n_ve_pos:TestPosConfigStockAvailability`
  → 88 en verde (toda la suite del módulo).
- Hoot en `pos_test_82634` (copia con el módulo instalado, Chrome headless):
  `l10n_ve_pos_self_order cuadrícula` → 3/3. Las suites `@pos_self_order`,
  `@point_of_sale` y `@l10n_ve_pos` dan los mismos fallos con y sin los
  parches de este cambio (fallos previos de esa base).
- Kiosko de `pos_consultor` (caja 2), con el ajuste activo:
  - Carga 9 plantillas en vez de 12: faltan "Opcion 5" (-1), "Producto Exento"
    (-13) y "Prueba 15684 Lampara" (-3) en WH/Stock. El buscador "Prueba
    15684" muestra "Breaker" y "Cable"; escanear 54321 ("Producto Exento")
    responde "No se encontró el producto" y 123456789 ("Producto IVA 16", 781)
    se agrega.
  - Reponiendo "Lampara" a 2 en WH/Stock y recargando el Kiosko, aparece.
  - Con un combo de prueba con "Lampara", "Producto Exento" y "Breaker" (1) y
    el catálogo visible: las dos sin stock llegan con
    `self_order_available = false` y no salen en la cuadrícula; en el combo
    salen como "Agotado" y tocarlas no las elige; escanear "Producto Exento"
    responde "El producto no está disponible".
  - Con "Lampara" en la categoría "Productos" y "Producto Exento" solo en una
    categoría propia: "Productos" muestra solo "Producto IVA 16" y la pestaña
    de la otra categoría no sale.
- Con el ajuste apagado vuelven las 12, las opciones del combo llegan
  disponibles, "Lampara" sale en "Productos" y la pestaña de la otra categoría
  aparece.
- Datos restaurados: "Lampara" en -3 y sin categoría, "Producto Exento" sin
  categoría, ajuste apagado, catálogo oculto de nuevo y el combo de prueba
  archivado. La categoría de prueba quedó vacía (no se borra con sesiones
  abiertas).
