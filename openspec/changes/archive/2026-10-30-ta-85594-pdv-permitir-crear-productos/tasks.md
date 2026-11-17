## 1. Implementación

- [x] 1.1 `pos.config.allow_product_creation_in_pos` (apagado por defecto, ver 3.2), related en
      `res.config.settings` y toggle en el bloque "POS Configuration" de Ajustes
- [x] 1.2 `PosStore.isProductCreationAllowed` (solo `true` enciende), `hasProductCreationAccess`
      y `editProduct()` sin producto
- [x] 1.3 "Crear manualmente" con `t-if` en la extensión de `point_of_sale.ProductScreen`
- [x] 1.4 Traducciones es_VE de la etiqueta y del help
- [x] 1.5 Tests `tests/test_pos_config_product_creation.py` (valor por defecto, guardado
      desde Ajustes, campo en la vista) y `static/tests/unit/product_creation.test.js`
      (getter, `editProduct` encendido/apagado/`undefined`, edición de un producto existente)
- [x] 1.6 Versión del manifest 19.0.1.28.0 (19.0 está en 1.26.0; la 1.27.0 la usa el PR del
      ticket 16064, #1545)

## 2. Verificación

- [x] 2.1 Instancia posconsultoria, base `posconsultoria_85594` (copia de `pos_consultor`),
      checkout local `local/posconsultoria-ta85594c` = `88b097b27` (ticket 16064) + esta rama.
      Al actualizar, las 7 cajas quedaron con la creación permitida (default anterior, `True`).
- [x] 2.2 Tests Python: `--test-tags /l10n_ve_pos:TestPosConfigProductCreation`, 3/3.
      En base nueva con solo `origin/19.0` + esta rama (`scripts/odoo-test l10n_ve_pos
      --container odoo-posconsultoria --addons .../odoo-venezuela/l10n_ve_pos --recursive`):
      125 tests, 0 fallos, 0 errores, 3 omitidos.
- [x] 2.3 Hoot `l10n_ve_pos creación de productos`: 6/6. El resto de `l10n_ve_pos/unit`
      tiene 18 fallos que ya estaban sin este cambio (mismos 18 con el checkout en
      `88b097b27`: `partner_list_searched_vat` y `pos_order_line_discount`).
- [x] 2.4 Navegador, Caja 1 con cajero manager: Ajustes muestra "Permitir crear productos"
      traducido; encendido, "Crear producto" abre "Nuevo producto"; apagado (después de
      "Volver a cargar datos") no aparece, `editProduct()` sin producto no abre nada y
      "Editar producto" sigue funcionando.
- [x] 2.5 "Crear manualmente" no se vio en el navegador: solo aparece con la pantalla de
      productos vacía, y la copia tiene productos. Que el PdV cargue prueba que el xpath de
      la extensión encuentra el botón; si se mostrara, lo frena el guard de `editProduct()`
      (cubierto por Hoot).

## 3. Cierre

- [x] 3.0 Revisión con el reviewer de Binaural (2026-10-30): sin bloqueantes. Se agregaron
      el readme, "Cargar muestra" en los non-goals, por qué va en `l10n_ve_pos`, el choque de
      `tests/__init__.py` con #1545 y la nota de "Crear manualmente" (2.5).

- [x] 3.1 Archivar el change y volcarlo en `openspec/specs/l10n_ve_pos/spec.md`
- [x] 3.2 (2026-10-30, ya con el PR #1550 abierto) El ajuste pasa a **apagado por defecto**,
      para evitar que se creen productos sin control. El getter cuenta como permitido solo
      un `true` explícito (una caja en caché sin el campo queda sin creación, igual que en la
      base). Tests Python y Hoot ajustados. Va en commits nuevos, sin reescribir la rama.
