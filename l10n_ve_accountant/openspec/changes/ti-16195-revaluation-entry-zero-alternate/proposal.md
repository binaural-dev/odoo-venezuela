# Fix: el asiento de ajuste de monedas no realizadas no debe mover la moneda alterna

Ticket: https://www.binauraldev.com/odoo/helpdesk/action-389/16195

## Why

Contabilidad › Revisión › Asientos de regularización › Monedas no realizadas
(reporte nativo `Unrealized Currency Gains/Losses` de `account_reports`)
ajusta al cierre, **solo en bolívares**, los saldos abiertos en dólares
(cuentas por cobrar, por pagar y bancos en USD) a la tasa del día de cierre, y
crea una reversión automática.

En moneda alterna no hay diferencia alguna: 100 USD siguen siendo 100 USD, solo
cambia lo que valen en bolívares. Pero el asiento quedaba con importes en la
moneda alterna:

- El asistente nativo (`_get_move_vals`) crea las líneas con
  `currency_id = USD`, `amount_currency = 0` y el ajuste solo en `debit`/`credit`.
- En `_get_foreign_value`, la rama 5 ("línea ya en moneda alterna") se descarta
  porque `amount_currency` es 0, y como el asiento no es factura cae en
  `_get_non_invoice_foreign_value`, que convierte los bolívares del ajuste a
  dólares con la tasa de la fecha (3.000 Bs a 330 = 9,09 USD).

Reproducido (factura de 100 USD a 300 Bs/USD, cierre a 330): el asiento dejaba
9,09 USD en la cuenta por cobrar y 9,09 USD en la ganancia cambiaria. Los
reportes en moneda alterna mostraban 109,09 USD por cobrar entre el cierre y la
reversión, y una ganancia en USD que no existe. Con la fecha de reversión
movida, o con un pago entre el cierre y la reversión, el efecto se extiende o
queda un saldo en USD sobre una factura ya pagada.

Hallazgo de la reproducción: la reversión copia el valor alterno del asiento,
no lo recalcula con la tasa de su propia fecha; por eso asiento y reversión
sumaban 0 en USD y **no** quedaba un residuo permanente. El defecto es el USD
fantasma durante el tramo entre el cierre y la reversión.

## What Changes

`l10n_ve_accountant` hereda `account.multicurrency.revaluation.wizard` y
sobrescribe `_get_move_vals`: tras `super()`, cada línea del asiento recibe
`not_foreign_recalculate = True` y `foreign_debit = foreign_credit = 0`.

`not_foreign_recalculate` es el mecanismo que la localización ya usa para
asientos de diferencia cambiaria, extractos bancarios y ajustes: lo respetan
`_skip_foreign_compute` (nivel línea) y el cálculo a nivel de asiento. La
reversión de `create_entries` copia las líneas con esa marca, por lo que
también queda en 0 sin código adicional.

## Capabilities

### New Capabilities
- `revaluation-entry-alternate-zero`: el asiento de ajuste de monedas no
  realizadas y su reversión ajustan solo la moneda de la compañía; todas sus
  líneas quedan con 0 en la moneda alterna.

## Impact

- Archivos: `l10n_ve_accountant/wizard/multicurrency_revaluation.py` (nuevo),
  `wizard/__init__.py`, `__manifest__.py` (versión).
- Pruebas: `tests/test_multicurrency_revaluation.py`.
- Cualquier cliente con la localización que use este reporte.
- **Posible corrección de datos:** los asientos de revaluación creados antes de
  este arreglo conservan importes alternos de más (no se corrigen solos). Si
  hay alguno contabilizado, se corrige con un asiento de regularización o un
  script; decisión de Producto.
- **Pendiente de Producto:** si el asistente de monedas no realizadas debe
  usarse en la localización y cómo interactúa con el pago revalorizado y la
  tasa máxima. Este cambio solo garantiza que, si se usa, no toca los alternos.
