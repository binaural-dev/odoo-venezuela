# Fix: el PdV no cargaba las listas de precios encadenadas más allá del primer nivel (l10n_ve_pos)

## Why

Reportado en producción (2doce / INVERSIONES MERCEBAR): la caja mostraba
**1,16 Bs en todos los productos del catálogo** en vez del precio real.

La configuración del cliente es el patrón venezolano habitual, y es correcta:

| Lista | Moneda | Contenido |
|---|---|---|
| `DETAL VEF` (operativa, la única disponible en la caja) | VEF | 1 item global `formula`, `base=pricelist` → `Detal Euro` |
| `Detal Euro` (intermedia) | EUR | 1 item global `formula`, `base=pricelist` → `BASE USD` |
| `BASE USD` (referencia) | USD | 9.857 items `fixed`, uno por producto |

Los precios fijos viven solo en la lista en divisa: es la forma de no reescribir
el catálogo cada vez que se mueve la tasa BCV. Los `list_price` de los productos
son un placeholder (1,0 en los 9.857).

**El servidor resuelve la cadena bien.** Verificado con
`product.pricelist._get_product_price`: 2,00 USD → 1,7340 EUR → 1.493,26 Bs.
Ventas y facturación nunca estuvieron afectadas; el problema era solo del PdV.

La causa está en QUÉ se carga en la caja, no en cómo se calcula. El core
(`point_of_sale/models/product_pricelist.py` :: `_load_pos_data_domain`) resuelve
las listas base **un solo nivel**:

```python
all_ids = config._get_available_pricelists().ids + pricelist_ids   # → [DETAL VEF]
referenced_base_pricelist_ids = self.env['product.pricelist.item'].search([
    ('pricelist_id', 'in', all_ids),        # solo busca en las disponibles
    ('base', '=', 'pricelist'),
    ('base_pricelist_id', '!=', False),
]).base_pricelist_id.ids                     # → [Detal Euro] y se detiene
return [('id', 'in', list(set(all_ids + referenced_base_pricelist_ids)))]
```

Encuentra `DETAL VEF → Detal Euro` y para. Nunca descubre
`Detal Euro → BASE USD`. Medido con `pos.session.load_data([])` en la base del
cliente: llegaban 2 listas y 2 items (los dos globales), **cero items de
`BASE USD`**.

Con el eslabón ausente, `rule.base_pricelist_id` llega vacío al navegador y en
`getPrice()`
(`point_of_sale/static/src/app/models/accounting/product_template_accounting.js`)
el `if (rule.base_pricelist_id)` interno no entra, así que el precio se queda en
`list_price`. Las dos conversiones EUR del nivel intermedio son inversas exactas
y se cancelan (×0,00116 × 861,19 = 1,0), y el resultado sale
`1,00 + 16% IVA = 1,16` — idéntico en todo el catálogo, que es exactamente el
síntoma reportado.

Falla **en silencio**: el alert del core ("Make sure all pricelists are available
in the POS") solo salta si la lista recursada llega vacía a `getPrice()`, y aquí
el `if` corta antes de llamar a la recursión.

Se descartó explícitamente que el cálculo en JS estuviera mal. `getPrice()`
convierte hacia la moneda de la lista antes de aplicar la regla y **de vuelta**
a la moneda del PdV después (dos bloques `needsCurrencyConversion` simétricos),
así que las cadenas entre monedas dan el mismo número que el servidor. **No hay
que parchear `getPrice`.**

Se encontró además un segundo hueco en la misma familia, que habría quedado
latente al arreglar solo el primero: la carga **on-demand** de productos
(`pos.session.get_pos_ui_product_pricelist_item_by_product`, usada por
`product.template.load_product_from_pos` cuando el cajero busca un producto que
no vino en la carga inicial) restringe los items a
`config._get_available_pricelists()`. Las listas base **nunca** pueden estar ahí:
`pos.config` exige que toda lista disponible tenga la moneda del PdV
(constraint en `pos_config.py`) y las listas base están justamente en otra
moneda. Así que cualquier producto que entre por búsqueda llegaba sin su precio
fijo, sin importar el límite de carga.

## What Changes

- **Nuevo `models/product_pricelist.py`**:
  - `_pos_expand_base_pricelists(pricelist_ids)`: calcula el **cierre
    transitivo** de las listas base siguiendo `base='pricelist'`, a cualquier
    profundidad. Nunca reexpande una lista ya vista, así que termina aunque los
    datos traigan un ciclo — defensa en profundidad, porque
    `_check_pricelist_recursion` ya impide crearlos por el ORM.
  - `_load_pos_data_domain()`: extiende el dominio del core al cierre. Ejecuta
    el dominio del core con `search` en vez de inspeccionar su forma, para
    seguir siendo correctos si el core cambia cómo arma la semilla (listas
    disponibles, presets, etc.).
  - `_pos_warn_absolute_amounts_in_chain()`: ver "Limitación conocida".
- **`models/pos_session.py`**: nuevo override de
  `get_pos_ui_product_pricelist_item_by_product()`. Llama al core y le **suma**
  los items de las listas base que el core excluye (más los registros de esas
  listas, sin los cuales el many2one `base_pricelist_id` no resuelve en el
  navegador). Se suma en vez de reimplementar el método para no heredar su
  mantenimiento; el dominio de los items extra es espejo del del core cambiando
  solo el conjunto de listas.
- **`models/__init__.py`**: registra `product_pricelist`.
- **Nuevo `tests/test_pos_pricelist_chain_loading.py`** (slice_b): reproduce la
  cadena Bs → EUR → USD de 3 niveles y fija el contrato — cierre transitivo,
  terminación con ciclos, listas e items en la carga inicial, items en la carga
  on-demand, y paridad con el cálculo del servidor.

## Verificación

Medido contra la base del cliente (`dosdoce`, 9.857 productos), antes y después:

| | antes | después |
|---|---|---|
| `product.pricelist` cargadas | 2 | **3** |
| `product.pricelist.item` cargados | 2 | **13** (11 de `BASE USD` + 2 globales) |

Se simuló `getPrice()` en Python usando **solo los datos que el loader entrega**
y se comparó contra `_get_product_price` del servidor para los 16 productos de
la sesión: **16/16 coinciden** (p. ej. ALIÑO PICADO PARADIS 150GR → 2.239,8891
Bs en ambos). Los 5 productos sin regla son los de servicio del PdV (Discount,
Tips, Deposit, Settle Due, Settle Invoice), que legítimamente no tienen item y
cuyo fallback a `list_price` es el comportamiento correcto.

## Impact

- **Capability**: `pos-chained-pricelist-loading` (nueva).
- **Módulo**: `l10n_ve_pos`, solo Python (loaders). No toca JS, ni vistas, ni
  añade campos. Requiere reinicio del servicio; no requiere `-u`.
- **Cambio de comportamiento visible**: en instalaciones con listas encadenadas
  de 2+ niveles, la caja pasa a mostrar el precio de la lista en vez del
  `list_price` del producto. En instalaciones con cadenas de un solo nivel (o
  sin cadena) no cambia nada: el cierre transitivo devuelve el mismo conjunto
  que el core.
- **`point_of_sale.limited_product_count` deja de ser un asunto de
  corrección.** Antes, un producto fuera del límite de carga nunca obtenía su
  precio fijo. Con el override on-demand, los productos que entran por búsqueda
  traen sus items. El parámetro vuelve a ser solo una palanca de rendimiento.
  (En la base del cliente estaba en 10, lo que agravaba el síntoma pero no era
  la causa.)
- **Costo**: una consulta extra por nivel de la cadena en la carga de sesión
  (cadenas típicas: 2-3 niveles), y una consulta extra en la carga on-demand
  solo si la cadena tiene listas base. Despreciable frente al resto del payload.
- **Riesgo de despliegue**: bajo. Ambos overrides solo **agregan** registros al
  payload; ninguno quita ni reescribe lo que el core ya entregaba.

### Paso de despliegue obligatorio: refrescar las cajas ya abiertas

Reiniciar el servicio **no basta** para las cajas que ya tienen la sesión
abierta en el navegador. El PdV guarda los datos en IndexedDB y en cargas
posteriores sincroniza de forma **incremental**: `pos.load.mixin
::_last_server_date_to_load` (`pos_load_mixin.py:42`) y
`product.pricelist.item::_server_date_to_domain` filtran por
`write_date > pos_last_server_date`.

Este fix amplía **qué listas** entran en el alcance del loader, pero los items de
la lista base ya existían y su `write_date` es viejo, así que el sync incremental
los descarta. Efecto observado tras desplegar: una ventana nueva (o incógnito)
muestra los precios correctos, mientras una caja ya abierta sigue mostrando el
`list_price` aunque el servidor esté corregido.

Hay que empujar el `write_date` de los items de las listas base para que el
siguiente sync los baje:

```sql
UPDATE product_pricelist_item SET write_date = now()
WHERE pricelist_id IN (<ids de las listas base de la cadena>);
```

`write_date` es metadata de auditoría: no altera precios ni contabilidad.

La alternativa por navegador (borrar IndexedDB: *Clear site data*, o el botón
"Delete all indexed DB" del widget de debug del PdV) sirve para una prueba
puntual pero no escala a varias cajas, y el widget de debug puede no estar
disponible si otro módulo rompe el bundle de assets del PdV.

### Limitación conocida

`models/res_currency.py` restringe a propósito las monedas que viajan al PdV
(compañía + moneda del PdV + divisa, "Avoids loading extra currencies present in
pricelists"), así que la moneda de una lista **intermedia** normalmente no se
carga. En `getPrice()` eso hace que `needsCurrencyConversion` sea falso y se
salten ambas conversiones de ese nivel.

Para reglas porcentuales es inocuo: son invariantes de escala y las dos
conversiones son inversas exactas — verificado en la cadena del cliente, donde
solo viajan VEF y USD (no EUR) y el resultado igual coincide con el servidor.

Pero `price_surcharge`, `price_round`, `price_min_margin` y `price_max_margin`
son montos **absolutos** en la moneda de la lista: sin conversión se aplicarían
en la escala equivocada. No se cambió el contrato de `res_currency.py` (tiene su
propia razón de ser y un test que lo fija); en su lugar
`_pos_warn_absolute_amounts_in_chain()` emite un warning al cargar la sesión si
alguna lista base usa esos campos, para que el caso no devuelva un precio
plausible y falso en silencio. Si algún cliente necesita recargos absolutos en
una lista intermedia, hay que resolver primero la carga de monedas de la cadena.
