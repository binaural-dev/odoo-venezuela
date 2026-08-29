# Feature: redondear el precio unitario del PdV a la moneda principal (l10n_ve_pos)

## Why

> **Nota de alcance (importante).** El problema real tenía **dos capas**, y la
> primaria NO es la de este change:
>
> 1. **Primaria — configuración del impuesto (fuera de este change).** La MF de
>    esta caja está fiscalizada en modo **"IVA excluido / suma"** (registra el
>    precio como base y le agrega el 16%; el tipo de tasa está **bloqueado**, no
>    se puede reprogramar por comando — se probó `PT…`/`Pt` tras un Reporte Z y
>    la máquina lo aceptó con ACK pero el `S3` no cambió). En cambio el impuesto
>    `16% Ventas` de Odoo estaba en `price_include = tax_included`, así que Odoo
>    mandaba el precio **con** IVA y la MF le sumaba el 16% otra vez → **doble
>    IVA** (S25: `subtotalBases = 23.519,56 = 20.275,48 × 1,16`). Ese desfase del
>    16% (miles de Bs) era el que tumbaba el cierre. **Se resolvió cambiando el
>    impuesto a `tax_excluded` (No incluido)**, para que Odoo trate los precios
>    de catálogo como **netos** (que es lo que la MF asume). Es un cambio de
>    **configuración/dato**, no de código de este módulo, pero es prerequisito
>    de este change.
> 2. **Secundaria — precisión (lo que resuelve este change).** Una vez alineado
>    el impuesto, queda el desfase de **1–2 céntimos** por el orden de redondeo
>    (abajo). Sin este fix, el `199` seguía dando NAK por ~2 cts en líneas con
>    cantidad > 1 y precio nacido de `$ × tasa`.
>
> Ambas capas hacen falta. Verificado en navegador (2doce-market, db `212`): con
> el impuesto en `tax_excluded` **y** este redondeo, la factura imprime completa
> y el `199` cierra (ACK). El desfase de 2 céntimos del texto de abajo se
> describe con el impuesto en su forma original (incluido); la mecánica del
> redondeo es idéntica en modo neto.

En una caja con pago en divisas, una factura del PdV (orden `C3-CCS - 000001`,
factura `00004961`) se imprimía en la máquina fiscal (MF) "hasta casi el final"
y se quedaba pegada. En consola:

```
TfhkaDriver::sendCommand - 199 NAK: la impresora rechazó el cierre.
Los montos 2XX no coinciden con subtotal+IVA+IGTF calculado por la impresora.
```

Causa raíz: un desfase de redondeo entre Odoo y la MF por el **orden** en que
cada uno redondea.

- La orden tiene una línea: `qty = 4`, `price_unit = 5068,865205` (con IVA;
  nace de `precio_$ × tasa BCV`, por eso arrastra 6 decimales — la DP
  "Product Price" es 6).
- **Odoo** hace *multiplicar y luego redondear*:
  `5068,865205 × 4 = 20.275,4608 → 20.275,46` = `amount_total`. Con IGTF 3%:
  `20.275,46 × 1,03 = 20.883,72` = `amount_paid`.
- La **MF** sólo acepta el precio de ítem con **2 decimales** (Flag 21=00,
  manual TFHKA "Manual de Protocolos y Comandos" V8.5.0, Tabla 22), así que
  recibe `5068,87` y hace *redondear y luego multiplicar*:
  `5068,87 × 4 = 20.275,48`. Su IGTF: `20.275,48 × 1,03 = 20.883,74`.

Los comandos de pago `2XX` que se le envían suman `20.883,72` (los de Odoo),
pero la impresora, con su propio cálculo (`20.883,74`), espera 2 céntimos más;
como el cierre `199` con Flag 50=01 sólo se acepta si `Σ(2XX) == base+IVA+IGTF`
de la impresora, la rechaza con NAK y el documento no se cierra ni se corta.
Al apagar/encender la MF aborta esa transacción abierta y vuelve a imprimir
normal.

Con `qty = 4` y 2 decimales el número `20.275,46` es **inalcanzable** para la
MF (`5068,86 × 4 = 20.275,44` o `5068,87 × 4 = 20.275,48`, nunca `,46`). La
única forma de que Odoo y la MF coincidan siempre es que **ambos partan del
mismo precio unitario a la misma precisión** — la de 2 decimales que impone la
máquina fiscal y que, además, es la que el cajero ya ve en pantalla.

## What Changes

### Frontend (PdV)

- `static/src/overrides/models/pos_order_line.js`: en el `setUnitPrice(price)`
  ya existente, tras `super.setUnitPrice(...)` y **antes** de derivar
  `foreign_price`, se redondea `this.price_unit` a la moneda en la que se
  cobra:
  - orden en moneda principal (caso VE normal, Bs) → `order.roundLocalMoney()`;
  - orden en moneda foránea (rama `_is_order_in_foreign_currency()`) →
    `order.roundForeignMoney()`.

  Ambos helpers redondean a `decimal_places` de la moneda (2 para Bs y $). Se
  hace en `setUnitPrice` porque es el único punto por el que se fija el precio
  unitario (aplicación de tarifa y precio manual), así que línea, IVA, IGTF,
  autocompletado de pagos, comando de la MF y factura quedan todos derivados
  del mismo valor de 2 decimales.

## Impact

- **Capability**: `pos-unit-price-currency-rounding` (nueva).
- **Módulo**: `l10n_ve_pos`. Sólo frontend
  (`static/src/overrides/models/pos_order_line.js`). No toca Python ni datos.
  Basta recargar assets (el contenedor `proj` corre con `--dev=all`,
  autoreload en caliente); **no** requiere `-u`.
- **Cambio de precio (intencional y global)**: el importe cobrado cambia en
  céntimos en **toda** venta, no sólo en las que van a la MF (p.ej.
  `20.275,46 → 20.275,48`). Es deliberado y aprobado: es lo correcto para un
  catálogo anclado en $ que se cobra en una moneda de 2 decimales, y elimina
  la incoherencia que ya se veía en pantalla (`5.068,87 × 4 = 20.275,48 ≠
  20.275,46` que mostraba el total).
- **Moneda foránea — no se rompe**: la regla del diseño (documentada en
  `pos_order_line.js` y en `pos_order.js::roundForeignMoney`) es que el local
  (Bs) es primario y el foráneo ($) se deriva con **una sola** conversión
  `order.localToForeign()`; la invariante `Σ(get_foreign_price_*) ==
  order.get_foreign_total_with_tax()` se conserva porque todo sigue saliendo
  del local. El $ mostrado no cambia de forma perceptible: `0,0048` Bs de
  redondeo convertidos a $ son `~0,000005`, muy por debajo del céntimo.
- **IGTF — no se rompe**: en `l10n_ve_pos_igtf` el IGTF se calcula **entero
  sobre el local** (`compute_igtf_amount = round(base × 3%)` con
  `res.currency.round`, base = `totalDue`) y su lado foráneo es una única
  conversión (`_igtfToForeign`), sin cálculo paralelo en $. Al redondear el
  unitario, `totalDue`, el IGTF y el total con IGTF se recalculan
  consistentes (`20.275,48 → IGTF 608,26 → 20.883,74`) y coinciden con lo que
  la MF espera → el `199` se acepta.
- **Factura (`account.move`)**: la línea de factura hereda el `price_unit` de
  la línea del PdV verbatim (verificado: hoy ambos son `5068,865205`), así que
  llega ya redondeado. La DP "Product Price" se mantiene en **6**, de modo que
  se almacena/mostrará como `5068,870000` (mismo valor, ceros de relleno). No
  se baja la DP a 2 (decisión del usuario).
- **Fuera de alcance / a vigilar**: las **líneas con descuento** meten una
  capa de redondeo extra (el descuento es %, lo aplican Odoo y la MF por
  separado). Este cambio elimina la causa principal (los 6 decimales del
  unitario); conviene probar además un caso con descuento por si reaparecen
  céntimos ahí. La corrección del clasificador `is1xx` en el driver de la MF
  (que hoy trata el NAK del `199` como "no fatal" y reporta éxito) es un bug
  aparte de `l10n_ve_mf_base`, no de este change.
