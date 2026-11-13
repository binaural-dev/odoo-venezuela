## Why

Tarea https://binaural.odoo.com/odoo/action-341/86066, ajuste de la regla de cobro en la moneda de
cobro (archivos de la fase 1 en `archive/2026-11-04-ta-86066-pdv-tercera-moneda`). En la caja 1 en Bs
de `pos_consultor` (06-nov, € a 1.004,9565776200 Bs), una orden de 18.560 Bs cobrada con € 25 dejó la
línea en 25.122,37 Bs en vez de 25 × 1.004,9566 = 25.123,91 Bs: el cliente recibió Bs 1,54 de menos de
vuelto.

`setTenderAmount` valoraba lo que cubre lo adeudado como el restante exacto más el excedente
convertido, y medía ese excedente contra lo adeudado ya redondeado a céntimos de euro
(18.560 / 1.004,9566 = 18,4685 → 18,47; 25 − 18,47 = 6,53 en vez de 6,5315). El error llega a medio
céntimo de la moneda de cobro, a favor o en contra según el redondeo de lo adeudado.

## What Changes

- **Pago justo** (lo tecleado igual a lo propuesto, comparado en la moneda de cobro con su redondeo): la
  línea vale el restante exacto de la caja, como antes. Ej.: 18.560 Bs y € 18,47 → 18.560 Bs.
- **Con excedente**: la línea vale lo tecleado por la tasa (`rates.toLocal`), con el signo del restante.
  Ej.: 18.560 Bs y € 25 → 25.123,91 Bs, vuelto 6.563,91 Bs. En un reembolso la tasa es la original.
- **Pago parcial**: sin cambios (`_getPartialTenderLocalAmount`).
- **Gancho del excedente** `_getOverpaidTenderLocalAmount`, como el del pago parcial.
  `binaural_pos_multicurrency` (integra-addons#3173) lo extiende para el cobro en Bs en una caja en
  otra moneda. Allí lo adeudado es el restante de la factura, exacto en Bs, y el excedente se sigue
  midiendo contra él: valorar lo tecleado entero mezclaría la factura con la caja.
- **Lo tecleado se redondea a la moneda de cobro** antes de compararlo y convertirlo. El teclado no
  limita los decimales: 8,475 € valían 8,475 € convertidos con `tender_amount` 8,48, y eso distorsionaba
  la tasa original de los reembolsos.

## Non-goals

- La moneda alterna (`set_foreign_amount`, USD en una caja en Bs) tiene el mismo problema y queda para
  después, por decisión del usuario (06-nov): "Lo de dólares no lo trataremos aún, puede ser después de
  resolver el de euros". Tampoco se toca su test de IGTF.
- El signo de un negativo tecleado en una venta no cambia: si no cubre lo adeudado queda en negativo;
  si lo cubre, toma el signo del restante (ya era así).
