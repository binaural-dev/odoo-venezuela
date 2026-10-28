## 1. Implementación

- [x] 1.1 Parche de `ProductTemplate.canBeDisplayed`: con el ajuste activo, oculta los almacenables sin variantes con stock a mano
- [x] 1.2 Quitar el getter `productsToDisplay` del parche de `ProductScreen` (en O19 vive en `PosStore`, nunca se ejecutaba)
- [x] 1.3 Loader de `product.product`: la clave `warehouse` de O17 la ignora `stock`; ahora contexto `location` con la
      ubicación de origen de la caja (ver 1.7)
- [x] 1.4 Ayuda del ajuste corregida y traducida en es_VE
- [x] 1.5 Versión del manifest 19.0.1.27.0
- [x] 1.6 `pos.session.load_data` + `pos.load.mixin._last_server_date_to_load`: con el ajuste activo, `product.template`
      y `product.product` se cargan sin el filtro por `write_date` (sesión nueva y entrada desde el backend traen el
      stock actual)
- [x] 1.7 Loader con `location=<ubicación de origen>` en vez de todo el almacén: la misma ubicación que "Cantidad en 0"
- [x] 1.8 Archivar el change y volcarlo en `openspec/specs/l10n_ve_pos/spec.md`

## 2. Tests

- [x] 2.1 `tests/test_pos_product_available_qty.py`: el loader manda la cantidad de la ubicación de origen y sus hijas,
      no la de otra ubicación del almacén ni la de otro almacén; la carga incremental sin el ajuste no reenvía la
      variante y con el ajuste la trae con el stock actual; solo los modelos de producto pierden el filtro;
      `load_data` marca el contexto según el ajuste
      (`odoo --test-tags /l10n_ve_pos:TestPosProductAvailableQty`: 9 en verde, más los 8 de "Cantidad en 0")
- [x] 2.2 `static/tests/unit/product_template_available_qty.test.js`: ajuste activo/apagado, almacenable con y sin stock,
      variantes, no almacenables, producto archivado o no disponible en el PdV
      y sin caja cargada (`/web/tests?filter=l10n_ve_pos%20ProductTemplate%20canBeDisplayed`: 7/7 en verde)
- [x] 2.3 Prueba en navegador en `pos_test_82634` (copia de `pos_consultor`, mismos productos y stock): con el ajuste
      activo, "Caja 1" oculta "Producto Exento" (-13), "Opcion 5" (-1) y "Prueba 15684 Lampara" (-3), también en la
      búsqueda, y muestra los almacenables con stock (incluido "Prueba 15684 Cable" con 0,3) y los no almacenables
- [x] 2.4 Refresco del stock antes de 1.6, cambiando el stock de "Prueba 15684 Lampara" con la caja ya cargada:
      en "Caja 1" (VEF) sigue oculta tras F5 y tras abrir desde el backend; en "Caja Operativa" (VEF) sigue oculta en
      una sesión nueva; en "Caja USD" sí aparece en la sesión nueva, porque `binaural_pos_multicurrency` recarga los
      productos completos en las cajas en otra moneda; en todas aparece tras "Volver a cargar datos" → "Limitado"
- [x] 2.5 Con 1.6: en "Caja 1", al abrir desde el backend, desaparece al agotarse (caché 2 → -3) y aparece al
      reponerse (-3 → 2); en "Caja Operativa", una sesión nueva sin `from_backend` pasa de la caché (5) al stock actual
      (0) y la oculta; sin variantes duplicadas. F5 con la sesión abierta sigue sin refrescar (documentado)
- [x] 2.6 Con 1.7, en `pos_consultor` (rollback): "Caja Operativa" recibe la cantidad de "Estante 1", la misma que
      valida "Cantidad en 0", y no la del almacén OPER

## 3. Decisiones

- [x] 3.1 2026-10-28: primero se decidió solo documentar que la caja no refresca el stock sin recargar los datos
      ("Volver a cargar datos" → "Limitado")
- [x] 3.2 2026-10-28: al comprobar que tampoco lo refresca una sesión nueva en una caja en la moneda de la compañía,
      se elige la opción A: recargar los productos completos en cada apertura con el ajuste activo, como
      `binaural_pos_multicurrency`; para F5 con la sesión abierta queda la recomendación de la recarga limitada
- [x] 3.3 2026-10-28: medir el stock en la ubicación de origen de la caja, como "Cantidad en 0", y no en todo el almacén
      (hallazgo del code review)
