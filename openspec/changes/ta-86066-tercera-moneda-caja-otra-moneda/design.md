## Contexto

`binaural_pos_multicurrency` desvía toda conversión de una caja en otra moneda a la tasa nativa
(`res.currency._get_conversion_rate`): `tender_currency_rates` y `_get_pos_currency_rate_pair` no se
consultan allí. Este módulo solo necesita dejar de bloquear esas cajas y no suponer que la caja está en
la moneda de la compañía en el cruce.

## Decisiones

- **Gancho por caja (`pos.config._get_tender_currency_error`) y no quitar el bloqueo.** Sin
  `binaural_pos_multicurrency`, una caja en otra moneda convertiría con tasas contra la compañía:
  `l10n_ve_pos` solo sigue sin admitirla. La regla de la alterna también es de la caja: en una caja en la
  moneda de la compañía tiene su flujo (`is_foreign_currency`); en una caja en EUR es una moneda de cobro
  más. El método llama a la validación de cada caja (`_check_tender_currency_methods`) y la caja a la
  suya al cambiar sus métodos.
- **Fallback del cruce desde la moneda de la compañía.** `amount` del cruce es el debe/haber, siempre en
  la moneda de la compañía. Convertirlo desde la moneda de la sesión era lo mismo en una caja en Bs y un
  error en una caja en USD.
- **Línea transitoria en la moneda del diario.** El diario transitorio de una caja en otra moneda está en
  esa moneda y recibe las ventas en ella (extracto o pago del cierre). Con la línea del cruce en la moneda
  de la compañía, la transitoria quedaba en cero en Bs con saldo en USD. Se corrigió el supuesto del
  plan: `l10n_ve_accountant` reemplaza la validación del core de "la cuenta fuerza una moneda"
  (`_check_constrains_account_id_journal_id`, solo exige la moneda del diario del asiento), así que no
  era un error al publicar sino un saldo en otra moneda sin contrapartida. Es un parámetro opcional con el
  patrón de `currency_amount`: un override con la firma anterior sigue funcionando con los métodos de
  siempre.

## Riesgos

- Un módulo que sobrescriba `_create_cross_move_for` o los constructores de líneas sin `**kwargs` recibe
  `transitory_amount_currency` solo en una caja en otra moneda con un método con moneda de cobro. En el
  repositorio solo lo sobrescribe `binaural_pos_close_multicurrency`, con `**kwargs`.
