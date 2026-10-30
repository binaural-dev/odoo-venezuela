## Why

Tarea https://www.binauraldev.com/odoo/project/614/tasks/85594 (proyecto Integra 3.0, hito
"Mejoras Vertical Ventas 4to Trimestre"): desde el PdV se pueden crear productos
con la opción "Crear producto" del menú ≡. La tarea pide que en Ajustes se pueda
establecer si eso está permitido o no.

En Odoo 19 el core muestra "Crear producto" según `PosStore.hasProductCreationAccess`:
el permiso de crear en `product.product` y, con `pos_hr`, además el rol manager
del empleado. No hay un ajuste por caja para apagarlo. Hay un segundo acceso,
"Crear manualmente" en la pantalla de productos vacía, que llama a
`PosStore.editProduct()` sin revisar ningún permiso.

## What Changes

- **Nuevo ajuste por caja** "Permitir crear productos" (`pos.config.allow_product_creation_in_pos`,
  `Boolean`, **encendido por defecto**), con su related en `res.config.settings` y
  un toggle en el bloque "POS Configuration" de Ajustes, junto a los demás de la
  caja. Mismo nombre en los dos modelos, como `amount_to_zero` o
  `sell_kit_from_another_store` (un nombre con prefijo `pos_` haría que
  `point_of_sale` registre un warning en cada guardado de Ajustes).
- **Apagado**, el PdV:
  - oculta "Crear producto" del menú (`hasProductCreationAccess` devuelve `false`);
  - oculta "Crear manualmente" (extensión de `point_of_sale.ProductScreen`);
  - no abre el formulario de producto nuevo si algo llama a `editProduct()` sin
    producto.
- Editar un producto existente (`editProduct(product)`) no cambia.
- **Solo un `false` explícito apaga la creación** (getter `PosStore.isProductCreationAllowed`):
  una caja con la sesión abierta antes de actualizar el módulo trae `pos.config`
  de IndexedDB sin el campo (`undefined`) hasta "Volver a cargar datos", y no debe
  perder la opción.
- Traducción es_VE de la etiqueta y del help.
- Tests Python (valor por defecto, guardado desde Ajustes, campo en la vista) y
  Hoot (getter y `editProduct`, también con el campo `undefined`).

## Non-goals

- **Pedir la clave de supervisor para crear**: es el flag
  `pos_create_product_require_supervisor_key` de `binaural_pos_hr` (integra-addons,
  misma tarea).
- **Crear productos desde el backend**: sigue con los permisos de siempre. El
  ajuste es solo del PdV.
- **"Editar" del popup de información del producto**: la tarea solo habla de crear.
- **"Cargar muestra"** de la pantalla de productos vacía: también crea productos,
  pero el core ya lo limita a quien es administrador del PdV y del sistema
  (`loadSampleData`).

## Impact

- **Por qué en `l10n_ve_pos`:** es un ajuste del PdV que no es fiscal, como el
  modo estricto de código de barras, los kits de otra tienda o "Cantidad en 0",
  que ya viven aquí. integra-addons no tiene un módulo base genérico del PdV, y la
  clave de supervisor de `binaural_pos_hr` (que depende de este módulo) se apoya
  en este ajuste.
- **Módulo tocado:** `l10n_ve_pos` (19.0.1.26.0 → 19.0.1.28.0; la 1.27.0 la usa el
  PR del ticket 16064, #1545: el que se mergee segundo debe subir su versión). Con
  #1545 también choca `tests/__init__.py`, porque los dos agregan una línea al
  final: se conservan las dos.
- **Despliegue:** `-u l10n_ve_pos`. Columna nueva en `pos_config`; al actualizar,
  las cajas existentes quedan con la creación permitida, como hoy.
- **Ajustes:** el toggle está en Ajustes → Binaural Settings → POS Configuration y
  se aplica a la caja elegida en ese bloque.
