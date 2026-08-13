# Capability: pos-chained-pricelist-loading

Carga en el Punto de Venta de listas de precios encadenadas a cualquier
profundidad, incluso cuando los eslabones están en monedas distintas a la de la
caja.

## Contexto

El PdV de Odoo 19 calcula los precios **en el navegador**, con los registros que
el servidor le precarga. Por eso la corrección del precio depende de que la
cadena completa de listas viaje al cliente, no solo la lista operativa.

En Venezuela la forma habitual de manejar precios es:

- La lista **operativa** está en Bs (la moneda de la caja y de la compañía) y es
  la única que puede estar en `pos.config.available_pricelist_ids` — el
  constraint de `pos.config` exige que toda lista disponible tenga la moneda del
  PdV.
- Los **precios fijos** viven en una lista de **referencia en divisa** (USD),
  para no reescribir el catálogo cada vez que se mueve la tasa BCV.
- Puede haber listas **intermedias** (p. ej. en EUR) entre ambas.

El `list_price` de los productos suele ser un placeholder sin valor comercial.

## Requisitos

### R1 — La carga inicial de la sesión incluye la cadena completa

`pos.session.load_data()` DEBE entregar todas las listas de precios alcanzables
desde las listas disponibles de la caja siguiendo items con
`base='pricelist'`, **a cualquier profundidad**, no solo el primer nivel.

Rationale: el core resuelve un solo nivel. Con un eslabón ausente,
`rule.base_pricelist_id` llega vacío al navegador, `getPrice()` cae a
`list_price` y no emite ningún error — el cajero ve un precio equivocado sin
señal alguna.

### R2 — El cierre transitivo termina siempre

El cálculo de la cadena DEBE terminar aunque los datos contengan un ciclo
(A→B→A): una lista ya visitada NO se vuelve a expandir.

Nota: `product.pricelist.item._check_pricelist_recursion` ya impide crear ciclos
por el ORM, así que este requisito es defensa en profundidad para datos cargados
por SQL. No es una configuración soportada.

### R3 — Los items de las listas base viajan con sus listas

La carga DEBE incluir tanto los `product.pricelist.item` de las listas base como
los registros `product.pricelist` correspondientes.

Rationale: sin el registro de la lista, el many2one `base_pricelist_id` del item
no resuelve en el `related_models` del navegador y se cae al mismo fallback
silencioso que R1 evita.

### R4 — La carga on-demand cubre las mismas listas que la inicial

Cuando el cajero busca un producto que no vino en la carga inicial,
`pos.session.get_pos_ui_product_pricelist_item_by_product()` DEBE entregar
también los items de las listas base de la cadena.

Rationale: el core restringe esa ruta a `config._get_available_pricelists()`, y
las listas base **nunca** pueden estar ahí (están en otra moneda, y el
constraint de `pos.config` lo prohíbe). Sin esto, el límite
`point_of_sale.limited_product_count` se convierte en un asunto de corrección y
no de rendimiento: todo producto fuera del límite quedaría sin precio.

### R5 — El precio en la caja coincide con el del servidor

Para un producto cuyo precio se resuelve por la cadena, el precio calculado en
el PdV DEBE coincidir con
`product.pricelist._get_product_price()` del servidor.

Rationale: es la única referencia que garantiza que el ticket, la factura y la
pantalla digan lo mismo.

### R6 — No se altera el cálculo del precio en el cliente

Esta capability NO modifica `getPrice()`
(`product_template_accounting.js`). El cálculo del core es correcto: convierte
hacia la moneda de la lista antes de aplicar la regla y de vuelta a la moneda del
PdV después, con dos bloques `needsCurrencyConversion` simétricos.

Rationale: queda escrito para evitar que un diagnóstico futuro vuelva a
sospechar del cálculo. El defecto estaba en **qué** se carga, no en **cómo** se
calcula.

### R7 — Los montos absolutos en listas intermedias no fallan en silencio

Si una lista base de la cadena usa montos absolutos en su propia moneda
(`price_surcharge`, `price_round`, `price_min_margin`, `price_max_margin`), el
sistema DEBE dejar constancia en el log.

Rationale: `res_currency.py` restringe a propósito las monedas que viajan al PdV,
así que la moneda de una lista intermedia normalmente no se carga y sus dos
conversiones se saltan. Para reglas porcentuales es inocuo (son invariantes de
escala y las conversiones son inversas exactas), pero un monto absoluto se
aplicaría en la escala equivocada. Preferimos un warning a un precio plausible
y falso.

## Fuera de alcance

- Cargar las monedas de toda la cadena en el PdV. Hoy `res_currency.py` las
  restringe deliberadamente; levantar esa restricción exige entender qué asume
  el JS del módulo sobre el conjunto de monedas y es un cambio aparte.
- Calcular el precio en el servidor para el PdV en vez de precargar el catálogo.
  Sería un cambio de diseño mayor y no hace falta para corregir este defecto.
