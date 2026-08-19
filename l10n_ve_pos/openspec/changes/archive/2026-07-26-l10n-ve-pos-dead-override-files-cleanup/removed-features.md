# Inventario de características que había en los ficheros eliminados

Este documento existe porque en esta migración ha pasado varias veces que
algo estaba comentado y luego **sí** hubo que migrarlo. Borrar el fichero
no debe borrar la memoria de qué hacía.

Para recuperar cualquiera de estos ficheros:

```sh
git show 8768f65d7^:l10n_ve_pos/static/src/overrides/<ruta>
```

(`8768f65d7` es el commit que los eliminó; la rama `19.0` también
conserva versiones anteriores de varios de ellos.)

Estados usados: **MIGRADA** (vive hoy en otro sitio), **SUPERADA** (la
V19 la resuelve de raíz, no hay que portar nada), **NO MIGRADA**
(característica real que hoy no existe — candidata a portar si se
necesita).

---

## `models/pos_model.js` (257 líneas, patch de `PosStore.prototype`)

Era el fichero con más contenido de todos. Tenía cuatro cosas distintas:

### 1. `_processData` — carga de `cities`, `prefix_vats` y `foreign_currency`

```js
this.foreign_currency = loadedData["res.currency"][1];
this.cities = loadedData["res.country.city"];
this.prefix_vats = loadedData["prefix_vats"];
```

- `cities` / `prefix_vats`: **SUPERADA**. Odoo 19 no admite claves
  top-level ad-hoc en el payload del PdV (rompe el `RecordStore`, ver
  `models/pos_session.py:19-26`). Hoy los datos viajan como campos del
  propio `res.partner` vía `_load_pos_data_fields` (`prefix_vat`,
  `city_id`, `models/res_partner.py`).
- `foreign_currency`: **MIGRADA**. Hoy es `pos.config.foreign_currency_id`
  (cargado desde `models/res_company.py`) y se consume en
  `overrides/utils/contextual_utils_service.js:12`.

### 2. `format_foreign_currency(amount, precision)`

Formateaba un importe con el símbolo de la moneda fuerte respetando
`position` (`after` → `123 $`, si no → `$ 123`).

**MIGRADA**: hoy es `env.utils.formatForeignCurrency`, inyectada
parcheando el servicio en `overrides/utils/contextual_utils_service.js`, y
consumida en `payment_status.js:63,67,71`, `payment_screen.js:29,60,213` y
`order_receipt.js:9`.

### 3. `update_products(order)` + `push_orders` / `push_single_order`

Refrescaba desde el servidor los `product.product` de las líneas de la
orden antes de enviarla, para validar existencias con datos frescos:

```js
const products = await this.orm.silent.call('pos.session',
    'get_pos_ui_product_product_by_params',
    [odoo.pos_session_id, { domain: [['id', 'in', product_ids]] }]);
this._loadProductProduct(products);
```

**NO MIGRADA.** `get_pos_ui_product_product_by_params` y
`_loadProductProduct` son API de V17 que no existe en V19 (el equivalente
sería `pos.data.read` / `callRelated`).

⚠️ **Consecuencia detectada**: los dos controladores de validación de
existencias siguen definidos en Python pero **nadie los llama desde el
frontend** en todo `src/`:

- `controllers/controller.py:13` → `/validate_products_order`
- `controllers/controller.py:39` → `/validate_products_in_warehouse`
  (con su parámetro `sell_kit_from_another_store`)

Es decir: la validación de existencias al enviar la orden **no está
operativa en V19**. Lo que sí quedó vivo es otra cosa, más simple: ocultar
del catálogo los productos sin stock (`product_screen.js:77`) y mostrar la
cantidad libre en la ficha (`product_card.js:48-52`). Si el negocio
necesita el bloqueo al pagar/enviar, hay que portar esta parte.

### 4. `compute_all(taxes, price_unit, quantity, currency_rounding, handle_price_include)`

Reimplementación completa (~200 líneas) del motor de cálculo de impuestos.

**NO MIGRADA, delta desconocido.** El cuerpo no contiene ni una
referencia a moneda foránea, IGTF ni tasa de cambio: los comentarios
numerados ("1) Flatten the taxes", "3) Iterate the taxes in the reversed
sequence order…") son literales del core de Odoo, así que era una copia
del `compute_all` nativo de V17 con alguna modificación local que no está
documentada. Si algún día aparece un descuadre de impuestos en el PdV,
el paso correcto es diffear ese cuerpo contra el `compute_all` de Odoo
17 para aislar el delta antes de portar nada. Hoy lo único que hay en
esa zona es un guard contra un bug del core V19 en `_computeAllPrices`
(`overrides/models/pos_order.js:787-805`), que es un problema distinto.

---

## `models/product_model.js` (19 líneas, patch de `Product.prototype`)

- `setup()` guardaba `this.originalTaxes = this.taxes_id`.
- `get_foreign_price(...)` multiplicaba el precio por
  `this.pos.get_order().get_conversion_rate()` cuando había moneda
  foránea.

**SUPERADA.** En V19 la conversión no se hace precio a precio: los
importes foráneos se derivan del importe local con **una sola**
conversión a nivel de orden/pago (regla registrada en
`openspec/migration-lessons.md`; ver `overrides/models/pos_order.js`).
`originalTaxes` no tiene hoy ningún consumidor.

---

## `screens/partner_list/partner_list.js` (35 líneas)

- `updatePartnerList(event)`: al pulsar **Enter** en el buscador, si
  había exactamente un resultado lo seleccionaba; si no había ninguno,
  abría directamente la creación de cliente.
- `createPartner()`: preseteaba `country_id` y `state_id` de la compañía y
  metía el texto buscado como `vat` del cliente nuevo.

**Parcialmente cubierta.** La precarga de localización desde la compañía
ya existe, y más completa (país, estado, ciudad, municipio, parroquia,
C.P.), en el `default_get` de
`openspec/changes/archive/2026-07-26-l10n-ve-pos-partner-quick-form-company-defaults/`.

**NO MIGRADO** el atajo de teclado: hoy Enter en el buscador de clientes
no crea el cliente ni arrastra el texto buscado como RIF. Es una mejora
de velocidad de caja real si se echa en falta.

---

## `screens/partner_list/partner_list.xml` (8 líneas)

Añadía `<th>Document</th>` a la cabecera de la tabla de clientes.

**SUPERADA / no aplicable.** La plantilla `point_of_sale.PartnerList` de
V19 ya no tiene `thead` ni `th`: es un `<table class="table table-hover">`
con componentes `PartnerLine` (ver
`addons/point_of_sale/static/src/app/screens/partner_list/partner_list.xml:27-52`).
La columna del documento que hoy añade el override **activo**
`screens/payment_line/partner_line.xml` no necesita cabecera, así que no
falta nada.

---

## `screens/product_screen/actionpad_widget.xml` (9 líneas)

Mostraba `(prefix_vat + vat)` junto al nombre del cliente en el actionpad
de la pantalla de productos:

```xml
<span t-if="props.partner.vat">
  (<t t-esc="props.partner.prefix_vat"/><t t-esc="props.partner.vat"/>)
</span>
```

**NO MIGRADA.** Hoy el botón de cliente del PdV solo muestra el nombre. Es
la anotación más fácil de reactivar si se echa en falta ver el RIF sin
abrir la ficha: `prefix_vat` ya se carga al frontend
(`models/res_partner.py`), así que solo haría falta la plantilla nueva
contra el componente V19 equivalente.

---

## `screens/product_screen/product_list.js` (25 líneas)

Filtraba del catálogo los productos sin stock según
`pos_show_just_products_with_available_qty`, con excepción para `service`
y `consu`.

**MIGRADA.** Vive en `overrides/screens/product_screen/product_screen.js:77`
(frontend) y `models/product_product.py:66` (servidor).

---

## `screens/payment_screen/payment_screen_top.js` (0 bytes)

Fichero vacío, sin contenido en ninguna versión. El override real es su
`.xml` hermano (`payment_screen_top.xml`, `t-name="PaymentScreenDue"`),
que sigue activo.
