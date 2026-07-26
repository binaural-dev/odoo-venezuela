# Tasks

## 1. Diagnóstico

- [x] 1.1 Barrer todo `static/src` contando líneas activas por fichero
      (no comentario, no vacías) para localizar los ficheros muertos: 4
      `.js` con cero líneas activas, 1 `.js` de 0 bytes y 2 `.xml` con
      solo el wrapper `<templates>`
- [x] 1.2 Comprobar que ningún módulo del despliegue (`l10n_ve_pos`,
      `l10n_ve_pos_mf`, `l10n_ve_pos_igtf`, `integra-addons`) los importa
      ni hereda sus plantillas — los únicos `import` que los mencionan
      están dentro de los propios ficheros comentados
- [x] 1.3 Verificar que los flags de configuración que consumían siguen
      teniendo consumidor vivo:
      `pos_show_just_products_with_available_qty`
      (`product_screen.js:77`, `product_product.py:66`) y
      `pos_show_free_qty` (`product_card.js:49`)
- [x] 1.4 Confirmar que `product_list.js` es un duplicado superado y no
      una característica desactivada (la lógica de filtrado por stock
      vive en `product_screen.js:77`)

## 2. Implementación

- [x] 2.1 Eliminar `overrides/models/pos_model.js` y
      `overrides/models/product_model.js`
- [x] 2.2 Eliminar `overrides/screens/partner_list/partner_list.js` y
      `partner_list.xml` (el directorio queda vacío y desaparece)
- [x] 2.3 Eliminar
      `overrides/screens/product_screen/actionpad_widget.xml` y
      `overrides/screens/product_screen/product_list.js`
- [x] 2.4 Eliminar el fichero vacío
      `overrides/screens/payment_screen/payment_screen_top.js` (el
      override vivo es su `.xml`)
- [x] 2.5 Comprobar que los ficheros vivos adyacentes siguen en su sitio:
      `screens/payment_line/partner_line.xml` (columna VAT en la lista de
      clientes) y `screens/payment_screen/payment_screen_top.xml`

## 3. Validación

- [ ] 3.1 `-u l10n_ve_pos` en el contenedor `proj` para reconstruir el
      bundle del PdV — pendiente, no ejecutado en este pase
- [ ] 3.2 Verificación en navegador (usuario): el PdV arranca sin errores
      en consola (un `import` colgante rompería el bundle completo)
- [ ] 3.3 Verificación en navegador (usuario): la pantalla de productos
      sigue filtrando por stock con
      `pos_show_just_products_with_available_qty` activo, y la lista de
      clientes sigue mostrando su columna de documento

## 4. OpenSpec

- [x] 4.1 `openspec validate l10n-ve-pos-dead-override-files-cleanup --type change --strict --no-interactive` →
      `Change 'l10n-ve-pos-dead-override-files-cleanup' is valid`

## 5. Pendiente (fuera de alcance de este change, con seguimiento)

- [ ] 5.1 Decidir qué hacer con `pos.config.validate_phone_in_pos`
      (`models/pos_config.py:37`): campo huérfano sin consumidor ni vista
      desde que se borró el editor de contactos V17 — implementar la
      validación de teléfono o eliminar el campo
- [ ] 5.2 Decidir qué hacer con
      `res.company.pos_show_free_qty_on_warehouse`
      (`models/res_company.py:12`): tiene campo, related en `pos.config` y
      bloque en los ajustes (`views/res_config_settings.xml:146-154`),
      pero ningún lector en Python ni en JS
- [ ] 5.3 Simplificar los globs de assets del manifest
      (`static/src/**/**`, `static/src/**/**/**/*` y la ruta explícita de
      `payment_model.js` describen el mismo conjunto)
