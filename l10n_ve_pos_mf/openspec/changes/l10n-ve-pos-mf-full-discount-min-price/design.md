# Diseño

## Contexto y restricciones

- La MF imprime en Bs; el mínimo representable de una línea es **0,01**. El
  driver descarta `price_unit <= 0`.
- `account.move.line.discount` tiene precisión de **2 decimales** (decimal
  precision `Discount`). `pos.order.line.discount` es float sin límite, pero al
  facturar se copia a la línea contable y se redondea a 2 decimales.
- `_check_max_discount` (l10n_ve_accountant) bloquea `discount >= 100%` en
  cualquier `account.move.line` con producto.

El requisito es que la **línea completa** (subtotal, no 0,01 por unidad) quede
en 0,01 conservando la cantidad. Con 2 decimales no se puede con un precio
unitario fraccionario (0,01/qty → 0,00). Se fija entonces `price_unit = 0,01` y
`discount = (1 − 1/qty) × 100`, de modo que subtotal = 0,01 × qty × (1/qty) =
0,01, con el descuento < 100% (no lo bloquea `_check_max_discount`) y el precio
> 0. Con cantidad < 0,5 (pesados) 0,01 × cantidad redondearía a 0,00: el
precio sube al céntimo siguiente de 0,01 / cantidad, sin descuento (0,3 kg →
0,04 → subtotal 0,01). La MF (precio × cantidad, 2 decimales) no puede repartir 0,01 entre N
unidades con el precio, así que con cantidad entera se le envían como
**N × 0,01 con un descuento por monto sobre el ítem de (N − 1) × 0,01** (`q-`
justo después del ítem): la línea fiscal suma 0,01 e imprime la cantidad real.
Con cantidad fraccionaria (pesados) van como **1 × 0,01** con la cantidad en la
descripción.

## Punto de intercepción único: `PosOrderline.setDiscount`

Todos los caminos de descuento terminan en `line.setDiscount(val)`:

- Descuento **por línea** (numpad `%`): `OrderSummary` → `pos.setDiscountFromUI`
  (gateado por `binaural_pos_hr`) → `line.setDiscount`.
- Descuento **global** (`pos_discount`): `_applyGlobalDiscountBeforeValidation`
  convierte el global a descuento por línea con `line.setDiscount(inferred)`.

Por eso el patch a `setDiscount` cubre ambos con una sola pieza.

### Algoritmo de `setDiscount`

1. Si el guard de re-entrada está activo, delegar directo al core.
2. `mfRestoreOriginalPrice()`: si la línea fue sustituida antes, restaurar su
   precio real (para evaluar el nuevo descuento sobre la base verdadera).
3. `super.setDiscount(discount)` (el core clampa a `[0, 100]`).
4. `mfEnsureNonZeroFiscalPrice()`: si con el descuento aplicado el neto
   redondea a 0 y el precio base es > 0, guardar el precio original, marcar
   `_mf_fiscal_min` y llamar a `_mfApplyLineFiscalMin()` (precio 0,01 +
   descuento (1−1/qty)×100 → subtotal 0,01).

El guard `_mf_fiscal_guard` evita recursión (las llamadas internas a
`setDiscount`/`setUnitPrice` no vuelven a entrar en la lógica). `setUnitPrice`
es el override de `l10n_ve_pos`, que actualiza también `foreign_price`.

### Cambio de cantidad y envío a la MF

- `setQuantity`: si la línea es `_mf_fiscal_min`, tras aplicar la cantidad se
  vuelve a llamar a `_mfApplyLineFiscalMin()` para recalcular el descuento y
  mantener el subtotal en 0,01 con la nueva cantidad.
- `PosStore.get_data_invoice` propaga `_mf_fiscal_min` a cada línea del payload;
  `_convertOrderForDriver` envía esas líneas a la MF como **N × 0,01** con
  `discount_amount = (N − 1) × 0,01`, y el driver (`l10n_ve_mf_base`,
  `printInvoice`) manda `q-<monto>` justo después del ítem (antes del subtotal
  `3`, el descuento aplica al último ítem). La línea fiscal suma 0,01, el cierre
  `199` cuadra con el pago y la MF imprime y registra la cantidad real.
  Con cantidad fraccionaria (pesados) no se sabe cómo redondea la MF
  0,01 × cantidad, así que va como **1 × 0,01** con la cantidad real antepuesta
  a la descripción (`_mfFiscalMinProductName`: `CANT 1,25 KG - PRODUCTO`).

## Interacción con el descuento global (Estrategia A)

`_applyGlobalDiscountBeforeValidation` **infiere** el porcentaje global del
monto de las líneas de `pos_discount`. Con líneas en el mínimo fiscal esa
inferencia falla: `pos_discount` calcula el monto sobre su subtotal de 0,01 y
la base de la inferencia es otra.

- **Aplicación manual** (`applyDiscount`, que pasa `expectedPercent`): se usa el
  **porcentaje tecleado** por el cajero en vez del inferido. La inferencia sólo
  se usa para ubicar las líneas de `pos_discount` que hay que borrar.
- `_resetGlobalDiscountOnLines` (`setDiscount(0)`) restaura los precios reales
  antes de aplicar el nuevo porcentaje.
- **Versión anterior (quitada):** restauraba los precios antes de inferir. Con
  eso, un 50% tecleado tras un global del 100% salía 0,01% (0,01 / 200).
- **Finalización** (`finalizeValidation`, sin `expectedPercent`): hace
  early-return cuando el global ya está aplicado, así que no deshace la
  sustitución.

## Reconocimiento por datos

`_mf_fiscal_min` y `_mf_zeroed_original_price` son propiedades en memoria. No
son campos: el core no las serializa, ni en IndexedDB ni al servidor. Por eso
se pierden en tres casos:

- al recargar la caja;
- en "Imprimir pedido pendiente", donde la orden viene del servidor;
- en las devoluciones.

Por eso `mfIsFiscalMinLine()` reconoce la línea de tres formas:

- por la marca;
- por sus datos (`_mfMatchesFiscalMinData`): precio 0,01 con el descuento
  exacto que corresponde a su cantidad, sólo con cantidad > 1. Esa
  combinación sólo la produce este módulo;
- por ser devolución de una línea así (`mfIsRefundOfFiscalMin`).

Se usa en tres puntos:

- `get_data_invoice`, para el payload de la MF;
- `mfEnsureNonZeroFiscalPrice`, que sólo marca, sin recalcular;
- `setQuantity`, que se evalúa antes de cambiar la cantidad y luego recalcula
  precio y descuento.

**`setUnitPrice`:** un precio puesto a mano (numpad, lista de precios) desmarca
la línea y olvida el precio original. Si no, la MF seguiría recibiendo 0,01 y,
al tocar luego el descuento, se restauraría el precio viejo.

**Limitaciones:**

- **Tras recargar no se conoce el precio original:** quitar el descuento deja
  la línea en 0,01 sin descuento, con MF y Odoo coherentes.
- **Pesados con cantidad ≤ 1:** no tienen descuento que los distinga, así que
  tras recargar van por la vía normal.
  - Con < 0,5 kg el precio subido deja precio × cantidad entre 0,01 y 0,015:
    la MF da 0,01 redondee o trunque.
  - Entre 0,5 y 1 kg depende de que la MF redondee (0,005–0,01) en vez de
    truncar.

## Respaldo en `pay()`

El caso normal se resuelve al **aplicar** el descuento (paso 4). El respaldo en
`PosStore.pay()` recorre las líneas y aplica `mfEnsureNonZeroFiscalPrice()`
antes de mostrar el pago, para cubrir órdenes cargadas/reanudadas cuyas líneas
ya venían con 100% (donde `setDiscount` nunca se invocó en esta sesión).

## Reversibilidad

`_mf_zeroed_original_price` guarda el precio de lista. Cualquier `setDiscount`
posterior (incluido `setDiscount(0)` al quitar el descuento, o el
`_resetGlobalDiscountOnLines` del global) restaura el precio antes de aplicar el
nuevo valor, dejando la línea como si nunca se hubiera sustituido.

## Compatibilidad con los modelos de MF (flag 21)

Fuente: *Manual de Protocolos y Comandos Venezuela* de The Factory HKA, V8.5.0
(23/08/2022). Las páginas citadas son las del manual.

### Qué es el flag 21

Es un flag que se programa en la MF y define **cómo interpreta la máquina los
dígitos** de los comandos: cuántos son enteros y cuántos decimales. Los
comandos no llevan coma decimal. Con los mismos dígitos `0000000100`:

| Flag 21 | Precio (enteros + decimales) | `0000000100` se lee como | `q-` (monto) |
|---|---|---|---|
| 00 | 8 + 2 | 1,00 | 7 + 2 |
| 01 | 7 + 3 | 0,100 | 7 + 2 |
| 02 | 6 + 4 | 0,0100 | 7 + 2 |
| 11 | 9 + 1 | 10,0 | 8 + 1 |
| 12 | 10 + 0 | 100 | 9 + 0 |
| 30 | 14 + 2 (montos grandes) | 1,00 | 15 + 2 |

(págs. 26-27, Tabla 22). La cantidad es 5 + 3 en todos, salvo con el 30
(14 + 3). La SRP-350 y la HKA-112 no admiten el 30 (pág. 26). KUBE y TD1125 lo
admiten con topes: precio ≤ 9.999.999.999,99 y cantidad ≤ 2.147.483,647
(pág. 27).

- **Afecta:** el precio unitario del ítem, la cantidad, el descuento o recargo
  por monto (`q-`) y los pagos.
- **No controla:**
  - Si el precio lleva IVA incluido. Eso es el tipo de tasa que se programa
    con `PT` (pág. 24).
  - Cuántos decimales se imprimen en el ticket.
  - Si se imprime el descuento.

  El manual no documenta ningún flag para esas tres cosas (pág. 81). Aun así
  aclara que los flags varían según el modelo (pág. 25).
- **Los totales de la MF siempre llevan 2 decimales**, sea cual sea el flag 21
  (pág. 57, S2).

### Relación con Odoo

- Cada caja tiene `pos.config.flag_21` ("Flag 21 - Formato de Números").
  Admite 00, 01, 02 y 30, con 00 por defecto.
- El driver (`TfhkaDriver.js`, `FLAG21_CONFIGS`) arma los dígitos de cada
  comando según ese valor. Coincide con la tabla del manual para esos cuatro
  valores.
- **Ese valor tiene que coincidir con el programado en la MF.** Si no
  coincide, la MF lee todos los precios desplazados (10, 100 veces). Eso rompe
  todas las ventas, no solo las líneas de mínimo fiscal.
- El driver actual no programa ni lee el flag de la MF: confía en el de la
  caja. El driver IoT anterior lo forzaba con `PJ21<valor>`
  (`l10n_ve_iot_mf/.../SerialFiscalDriver.py`).
- **Cómo saber el valor real de la MF** (a mano, al configurar la caja):
  - el botón **PROGRAMACION** del widget de debug del PdV envía `D` e imprime
    los flags y el firmware;
  - también el Fiscalizador, pestaña "Diagnóstico S3" → "Leer S3" (el
    flag 21 es el 22.º, contando desde 00);
  - o preguntarle al técnico de HKA que programó la máquina.
- Para ver el valor programado:
  - el comando `D` imprime los flags y la versión de firmware (pág. 29);
  - también se puede leer con `S3` (pág. 64, Tabla 53).

### Veredicto para esta solución

La línea de mínimo fiscal se envía como ítem `N × 0,01` seguido de
`q-` (N − 1) × 0,01.

- **Funciona con el flag 21 en 00, 01, 02 y 30**, en todos los modelos de la
  tabla del flag 21:
  - 0,01 y el monto del `q-` se representan exactos.
  - No se envía ningún tercer decimal.
- **El `q-` justo después del ítem, antes del subtotal `3`, rebaja ese
  ítem.** Aplica a todos los modelos; su formato depende del flag 21, no del
  modelo (pág. 27). El manual lo muestra en el ejemplo de las págs. 34-35: un
  ítem de 30,00 seguido de `q- 10,00` deja la base imponible en 20,00. También
  es válido en nota de crédito (pág. 37).
- **Con el flag 21 en 11 o 12 no funciona**, porque 0,01 no se puede
  representar (mínimo 0,1 o 1). Odoo no ofrece esos valores; una MF programada
  así fallaría en todas las ventas.
- **Precisión:**
  - En la MF física (C1-CCS) se imprimió `10 x Bs 0,009`, que es el descuento
    repartido por unidad (0,09 / 10). Es el formato de impresión de ese
    firmware y la línea neta quedó en 0,01.
  - El manual no documenta cómo se imprime un descuento sobre un ítem con
    cantidad mayor que 1.
  - A la MF solo le llegan 0,01 y 0,09, con 2 decimales. Una máquina de
    2 decimales no recibe nada que no pueda representar.

### Flags 11 y 12: fuera del alcance de la integración

La integración del PdV sólo soporta el flag 21 en 00, 01, 02 y 30:

- la selección de `pos.config.flag_21` no ofrece otros valores;
- el driver sólo tiene formatos (`FLAG21_CONFIGS`) para esos cuatro.

Una MF programada con 11 o 12 no se puede usar con este PdV: todos los precios
se leerían desplazados, no sólo los de las líneas de 0,01. Por eso no hay
control ni aviso para esos valores.

Si algún día se agregan 11/12 a la selección y al driver, hay que revisar el
mínimo fiscal: con 11 el precio mínimo es 0,1 y con 12 es 1, así que 0,01 no
es representable.

Descartado:

- **Leer el flag con `S3` antes de cada impresión:** hacía más lento el
  proceso.
- **Avisar al teclear el 100% según `pos.config.flag_21`:** con la selección
  actual nunca podía dispararse.

### Nota de crédito de líneas en el mínimo fiscal

El core crea las líneas de la devolución copiando el precio (0,01) y el
descuento de la original, sin pasar por `setDiscount`. Por eso esas líneas no
quedan marcadas.

- Con 3 o más unidades, el respaldo de `pay()` las detectaba y recalculaba el
  descuento con la cantidad devuelta.
- Con 2 unidades el neto por unidad redondea a 0,01 y no se detectaban.

`mfIsRefundOfFiscalMin()` las reconoce por la línea original (precio 0,01 con
descuento) y sólo las marca, sin tocar precio ni descuento. Así el subtotal de
la devolución es el mismo que se facturó.

La MF las recibe como N × 0,01 con `q-` (N − 1) × 0,01. `printCreditNote` ahora
envía ese `q-`; antes lo ignoraba.

**Limitación:** en una devolución parcial (k de N unidades), Odoo calcula
0,01 × k / N, que redondea a 0,00 o 0,01, mientras la MF recibe 0,01.

### Riesgos no cubiertos por el manual

- **SRP-280 y SRP-270:** no aparecen en la tabla del flag 21.
- **Otro firmware:** alguno podría repartir el descuento por unidad y
  redondearlo (0,009 → 0,01). En ese caso la línea quedaría en 0 o la MF
  rechazaría el comando. El manual no lo documenta; solo se descarta probando.
- **Si la MF rechaza el `q-`:** el driver aborta la transacción, así que el
  documento no queda a medias.
- **Cantidades muy grandes (más o menos 15.000 o más):** es un límite del lado
  de Odoo. El descuento redondeado a 2 decimales (tope 99,99%) deja el
  subtotal en 0,00 o 0,02 mientras la MF recibe 0,01 exacto.

### Verificación recomendada por familia

Probar en al menos una MF de cada familia:

- SRP-812, HKA-80, DT-230, PP9;
- SRP-350, HKA-112, HSP7000, TD1125, KUBE.

Pasos:

1. Imprimir `D` para ver el flag 21 y el firmware.
2. Emitir facturas con N = 2, 10 y 1000.
3. Probar tanto con tasa G como exento.
4. Comprobar que cada comando responde ACK.
5. Comprobar que el cierre `199` cuadra.
6. Revisar cómo se imprime la línea.

## Alternativas descartadas

- **Capar el porcentaje** para dejar neto 0,01: inviable por la precisión de 2
  decimales del descuento en factura (redondea a 100% → re-bloquea).
- **Enviar a la MF sólo la cantidad real (N × 0,01, sin descuento)**: la MF
  calcula precio × cantidad y la línea sumaría N × 0,01, no 0,01. No cuadraría
  con el pago y el `199` no cerraría.
- **Precio unitario 0,01 / N**: no cabe en 2 decimales con el flag 21 en 00.
  Cambiar el flag a 01 o 02 afecta a todas las ventas de la caja, y tampoco
  cubre cualquier N.
- **Descuento porcentual `p-` sobre el ítem**: usa 2 + 2 dígitos (pág. 34), no
  puede expresar (1 − 1/N) exacto y el manual no documenta su redondeo. `q-`
  (monto exacto) es más seguro.
- **1 × 0,01 con la cantidad en la descripción** (`CANT 2 - PRODUCTO`):
  funciona en cualquier MF, pero la cantidad es sólo texto. La memoria fiscal
  registra 1 unidad y no se ve el descuento. Se conserva sólo para cantidades
  fraccionarias (pesados).
- **Sólo hacer floor en el payload de la MF**: la MF imprimiría 0,01 pero la
  orden/factura seguiría en 0,00 con 100% → la bloquearía `_check_max_discount`
  y el cierre `199` no cuadraría con el pago (0,00 vs 0,01).
- **Relajar `_check_max_discount`**: fuera del alcance (vive en
  `l10n_ve_accountant`, no en un módulo de MF).
