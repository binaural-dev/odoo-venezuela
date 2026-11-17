## Contexto

El bloque `coversDue` de `setTenderAmount` (`l10n_ve_pos/static/src/overrides/models/payment_model.js`)
se copió de `set_foreign_amount`. Allí sumar el excedente al restante evitaba los céntimos fantasma de
un pago justo, pero con excedente arrastra el redondeo de lo adeudado.

## Decisiones

- **Tres ramas en vez de una.** El pago justo conserva el restante exacto (el motivo original de la
  regla); el excedente se valora como lo tecleado por la tasa. No deja céntimos pendientes con lo
  adeudado de `_getTenderDue` de este módulo: lo tecleado supera lo propuesto en al menos un céntimo y
  lo propuesto difiere del restante convertido en a lo sumo medio céntimo.
- **Gancho `_getOverpaidTenderLocalAmount` y no una red de seguridad.** `binaural_pos_multicurrency`
  extiende `_getTenderDue` para el cobro en Bs en una caja en otra moneda: lo adeudado es el restante de
  la factura, exacto en Bs, que puede diferir del restante de la caja en más de medio céntimo de la caja
  (IVA redondeado por línea). Valorar ahí lo tecleado entero mezcla las dos referencias, en los dos
  sentidos: con la factura por encima de la caja, Bs 0,01 de más daba $ 0,03 de vuelto; por debajo,
  Bs 45 de más no daban vuelto. Una red ("si la conversión no cubre el restante, la regla anterior")
  solo corregía el segundo caso y dejaba un salto en el vuelto. Medir el excedente contra la factura no
  tiene el error que se corrige aquí, porque la factura no es una conversión redondeada. Por eso MC
  conserva la regla anterior con el gancho, y en este módulo no hay red.
- **Redondear lo tecleado a la moneda de cobro.** Lo comparado, lo convertido y `tender_amount` son el
  mismo monto. La tasa original de un reembolso (`get_refund_tender_rates`, Σ|amount| / Σ|tender|) ya no
  se distorsiona con un tercer decimal.
- **Signo del restante.** Como en el pago parcial: un reembolso tecleado sin "-" sigue siendo una
  salida, y en un reembolso la tasa es la original (`_getTenderRates`, `getRefundTenderRate`).
- **Sin cambio de versión de `l10n_ve_pos`.** Solo cambia JS del PdV (sin datos ni vistas), en el mismo
  PR #1569, que ya sube a 19.0.1.30.0 sin publicar.

## Riesgos

- Un pago con excedente en euros da hasta medio céntimo de euro distinto al de antes (en Bs, hasta
  medio céntimo por la tasa). Es la corrección buscada.
- En una caja en otra moneda, el excedente en una tercera moneda (EUR en la caja USD, USD en la caja EUR)
  también se valora como lo tecleado convertido: allí lo adeudado sigue siendo la conversión redondeada
  del restante y tenía el mismo error. El cobro en Bs conserva su regla (gancho de MC).
- `binaural_pos_multicurrency` llama a un gancho nuevo de `l10n_ve_pos`: los dos PRs salen juntos, como
  ya exige el aviso de despliegue (primero odoo-venezuela).
