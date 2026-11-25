## Why

Tarea https://binaural.odoo.com/odoo/action-341/86066 (proyecto Integra 3.0, hito "Mejoras Vertical
Ventas 4to Trimestre"): "El POS no convierte con la tasa del euro el pago en Efectivo EUR: toma el
monto como dólares". Al cobrar con un método "Efectivo EUR" el PdV toma la cifra tecleada como
dólares, la línea sale con "$", la venta queda con saldo pendiente y los asientos cuadran en Bs y en
USD pero con el monto equivocado.

El motivo es que el PdV solo conoce dos monedas además de la suya:

1. `pos.config._get_pos_conversion_rate` y su espejo `pos_order.js::_getPosConversionRate` solo
   convierten moneda de la caja ↔ alterna; cualquier otro par devuelve 0.
2. `is_foreign_currency` significa "la alterna de la compañía" (USD): un método "Efectivo EUR"
   marcado así cobra con la tasa del USD y el formato del USD.
3. El core exige que el diario del método esté en la moneda de la caja o sin moneda
   (`pos.config._check_currencies`), así que no hay de dónde sacar el EUR.
4. El cruce al diario real (`_line_vals_move_cross_incoming/_outgoing`) pone `amount_currency` en la
   alterna solo si el diario real está en la alterna; con una Caja EUR pondría los Bs como euros.
5. `res.currency` solo carga la moneda de la compañía, la de la caja y la alterna, y se cachea por
   `write_date`: una tercera moneda no llegaría o llegaría vieja.

Decisiones con el usuario (2026-11-02, opciones recomendadas del plan): la moneda de cobro vive en
`l10n_ve_pos` (no en `binaural_pos_multicurrency`), se declara con un campo explícito en el método, el
cajón en esa moneda es un modelo nuevo en `binaural_pos_close`, el reembolso devuelve la moneda de
cobro a la tasa con la que se cobró y el vuelto sigue en la moneda de la caja. Primero la caja en la
moneda de la compañía; la caja en otra moneda (`binaural_pos_multicurrency`) se aborda después.

## What Changes

- **Moneda de cobro del método** (`pos.payment.method.tender_currency_id`, "Tercera moneda de
  cobro"): una moneda distinta de la de la compañía y de la alterna. Validaciones: no se combina con
  `is_foreign_currency` ni con un método de crédito, sus dos diarios de cruce son obligatorios
  (segunda revisión, S8: sin ellos el cruce se omitía en silencio), el `cross_journal` debe estar en
  esa moneda y solo se usa en cajas en la moneda de la compañía (restricción en `pos.config` y en el método): sus
  tasas son contra la moneda de la compañía. El diario del método sigue siendo el transitorio en la
  moneda de la caja.
- **Motor de conversión**: `pos.config.tender_currency_rates` (Json calculado) trae la tasa del día de
  cada moneda de cobro con `res.currency.rate.compute_rate` de la compañía de la caja
  (`with_company`), con la misma orientación que
  `foreign_rate` / `foreign_inverse_rate` (moneda → caja la GRANDE, caja → moneda la CHICA).
  `_get_pos_conversion_rate` y `_getPosConversionRate` convierten con ellas cuando un lado es una
  moneda de cobro: `(from → caja) × (caja → to)`, sin redondear la tasa. Los pares de siempre siguen
  la regla de siempre. Sin tasa del día devuelve 0.
- **Carga al PdV**: el loader de `res.currency` incluye las monedas de cobro y `res.currency` se
  carga siempre entero (sin el filtro por `write_date`).
- **Pago** (`pos.payment.tender_currency_id` / `tender_amount`, los mismos campos que ya tenía
  `binaural_pos_multicurrency`): lo cobrado en la moneda de cobro. En el PdV, `PosPayment` gana
  `getTenderCurrency`, `setTenderAmount` (si lo tecleado cubre lo adeudado, la línea vale
  exactamente el restante más el excedente convertido, como `set_foreign_amount`) y los ganchos
  `_getLocalDueBefore`, `_getTenderDue` y `_getPartialTenderLocalAmount`. La pantalla de pago propone
  lo adeudado en esa moneda, el teclado trabaja en ella, la línea se ve "€ X / Bs Y", el panel de
  estado muestra el restante en esa moneda y el recibo el monto cobrado junto al método. Sin tasa del
  día la línea no se agrega y se avisa. La línea de pago (`payment_line.xml`) envuelve el bloque de
  siempre en la rama de la moneda de cobro (`t-if getTenderCurrency()` / `t-else`) y conserva el
  `t-if` de `is_foreign_currency`, que es el ancla de `binaural_pos_multicurrency`. Un pago ya guardado
  usa su propia `tender_currency_id` (segunda revisión, S4): el recibo reimpreso muestra los euros con
  que se cobró aunque después cambie la moneda del método.
- **Servidor**: `_process_saved_order` (lo usan la sincronización del PdV y el asistente de pago del
  backend, `pos.make.payment`) completa la moneda del método (la orden serializa sus pagos anidados
  sin `serializeForORM`) y, si falta, el monto: a la tasa de la caja, o en un reembolso a la de los
  cobros de las órdenes originales de todas sus líneas (segunda revisión, S12: antes solo la de
  `refunded_order_id`, la primera); `_align_foreign_signs` alinea el signo de `tender_amount`;
  `get_refund_tender_rates` da la tasa de los cobros originales para el reembolso. La vista de
  `pos.payment` muestra la moneda y el monto cobrados.
- **Cobro desde el backend sin tasa del día** (segunda revisión, A1): `pos.make.payment.check`
  rechaza un método con moneda de cobro sin tasa del día de esa moneda, con el mismo aviso del PdV
  (antes guardaba 0 € sin avisar). La sincronización no se bloquea: si la conversión da 0, lo deja en
  el log del servidor.
- **Cruce**: un método con moneda de cobro cruza como uno en divisa (`_is_cross_move_eligible`), y la
  línea del diario real en esa moneda lleva `amount_currency` = lo cobrado en ella
  (`currency_amount` en `_create_cross_move_for`). Solo se pasa para esos métodos, así un override
  con la firma anterior sigue funcionando con los demás; si un llamador no lo pasa, se convierte el
  monto a la tasa del día de la caja.
- **Cruce combinado en dos patas** (revisión, 2026-11-03): con `split_transactions` apagado sigue
  siendo un asiento por método y sesión, pero con una pata de entradas y otra de salidas, cada una
  neteada por separado (`_get_combined_cross_legs`, `_create_combined_cross_move`). Con un solo neto,
  una venta de hoy y un reembolso a una tasa vieja dejaban el neto en Bs y el de la alterna o los
  euros con signos opuestos (el cierre chocaba con `account_move_line_check_amount_currency_balance_sign`),
  y un neto 0 en Bs con divisas de diferencia no cruzaba nada. Aplica también al USD de siempre. Cada
  pata arma sus líneas con la tasa de sus pagos (segunda revisión, S7); es informativa: la línea
  guardada toma la `foreign_rate` del asiento (related de `l10n_ve_accountant`).
- **Apertura**: el primer método de efectivo de la caja no puede ser uno en moneda de cobro (ahí van
  el vuelto y el arqueo del core).
- **`l10n_ve_pos_igtf`**: `_getLocalDueBefore` toma el mismo restante que su ajuste de
  `set_foreign_amount` (base de factura pendiente + deuda IGTF); los dos usan la misma condición
  (`hasIgtfContext`, segunda revisión, S9).

## Non-goals

- Caja en otra moneda con métodos en una tercera moneda (`l10n_ve_pos` los bloquea).
- Vuelto en la moneda de cobro: el vuelto sale del primer efectivo, en la moneda de la caja.
- Código fiscal del pago en EUR en la máquina fiscal (`l10n_ve_pos_mf`): configuración del
  implementador.
- Columnas en EUR en los reportes de pagos y de detalle de ventas.

## Impact

- **Módulos:** `l10n_ve_pos` 19.0.1.28.2 → 19.0.1.29.1 (campo nuevo: `-u l10n_ve_pos`),
  `l10n_ve_pos_igtf` 19.0.1.5.0 → 19.0.1.5.2 (solo JS y su bundle de pruebas Hoot).
- **Despliegue:** odoo-venezuela primero e integra-addons después, en la misma ventana, con
  `-u l10n_ve_pos,l10n_ve_pos_igtf,binaural_pos_multicurrency,binaural_pos_close,binaural_pos_close_multicurrency`.
  Con odoo-venezuela solo, el PdV sigue funcionando con el `binaural_pos_multicurrency` anterior
  (probado), pero no hay que configurar la moneda de cobro hasta actualizar integra-addons. Al revés no
  se puede.
- **Cruces combinados:** una sesión con ventas y reembolsos del mismo método crea ahora un asiento de
  cuatro líneas (entradas y salidas) en vez de dos con el neto; el neto que pasa a cada cuenta es el
  mismo.
- **PR abierto odoo-venezuela#1529** (tasa del día de Venezuela al facturar): no toca manifiestos. De
  los archivos de este cambio toca `l10n_ve_pos/models/pos_order.py` (`_prepare_invoice_vals`),
  `pos_payment.py` (`_create_payment_moves`) y el final de `tests/__init__.py`, en hunks distintos a
  los de este cambio salvo ese final, que resuelve el que se mezcle segundo. Fuera de ellos agrega un
  helper en `l10n_ve_rate/models/res_currency_rate.py` (`tender_currency_rates` llama a
  `compute_rate` con una fecha, no le afecta) y toca `l10n_ve_pos_igtf/models/pos_payment.py`, que
  este cambio no toca.
- **integra-addons (mismo despliegue):** `binaural_pos_multicurrency` hereda la moneda de cobro de
  `l10n_ve_pos`, `binaural_pos_close` agrega el cajón en la moneda de cobro y
  `binaural_pos_close_multicurrency` acepta el argumento nuevo del cruce.
- **Configuración del método "Efectivo EUR":** diario transitorio sin moneda, "Tercera moneda de
  cobro" = EUR, Diario de cruce = la caja real en EUR (con sus transitorias y sus cuentas de pago) y
  diario de la cuenta de cruce. Quitar `is_foreign_currency` si estaba marcado. Tasa del día del EUR
  cargada.
