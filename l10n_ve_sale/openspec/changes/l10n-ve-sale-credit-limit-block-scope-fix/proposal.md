# Ejecutar el chequeo de límite de crédito en `action_confirm` sin depender de `not_allow_sell_products`

Tarea: [TA-81707](https://www.binauraldev.com/odoo/action-341/81707) — asociado como fix descubierto durante esa tarea, no un ticket de soporte separado.

## Why

`action_confirm()` (`l10n_ve_sale/models/sale_order.py`) tiene el bloque que
valida el límite de crédito del cliente (`account_use_credit_limit` +
`use_partner_credit_limit_order`) anidado **dentro** de
`if self.env.company.not_allow_sell_products:`. Esa opción de compañía
controla si se valida el stock disponible antes de confirmar un presupuesto
— un concepto sin relación con crédito — y su valor por defecto es `False`.

Consecuencia real: en cualquier compañía VE con `account_use_credit_limit`
activo pero `not_allow_sell_products` desactivado (la configuración estándar
para la enorme mayoría de instalaciones), **el chequeo de límite de crédito
en presupuestos/pedidos nunca se ejecuta**. El equivalente en facturación
(`l10n_ve_accountant.action_post`) sí es independiente y sí bloquea — hoy es
posible confirmar un presupuesto muy por encima del límite del cliente sin
ningún aviso, y solo enterarse al intentar postear la factura resultante.

No hay ningún test que cubra el chequeo de crédito en este módulo — el bug
pasó varias versiones (hasta la actual `19.0.1.0.6`) sin detectarse.

Encontrado durante la investigación de la elevación a producto de "límite de
crédito en moneda alterna" (ver
`integra-addons/binaural_credit_limit/openspec/changes/binaural-credit-limit-foreign-currency/`),
que necesita que este chequeo corra de verdad para poder hacerlo
currency-aware — hoy estaría escribiendo una fórmula que en la práctica
nunca se ejecuta.

## What Changes

- El bloque de límite de crédito se saca de adentro del `if
  not_allow_sell_products` y pasa a evaluarse siempre (sujeto a sus propios
  gates: `account_use_credit_limit` y `use_partner_credit_limit_order`),
  igual que ya ocurre en `l10n_ve_accountant.action_post`.
- Se agrega un context flag propio, `skip_credit_limit_check` — mismo
  nombre y semántica que el que ya usa `l10n_ve_accountant` — para que un
  flujo con autorización explícita pueda saltear el chequeo sin tener que
  reutilizar `skip_not_allow_sell_products_validation` (que salta también
  la validación de stock, sin relación).
- `skip_not_allow_sell_products_validation` sigue existiendo tal cual, sin
  cambios de comportamiento para la validación de stock.

## Non-goals

- No se toca la fórmula de comparación en sí (`partner.credit +
  order.amount_total > partner.credit_limit`, sin conversión de moneda) —
  eso es alcance de la elevación a producto en
  `integra-addons/binaural_credit_limit`, que consume este fix como
  prerequisito.
- No se corrige aquí el mismo tipo de problema si aparece en otro lado del
  código VE — este proposal cubre únicamente `l10n_ve_sale.action_confirm`.

## Impact

- **Módulo**: `l10n_ve_sale` (`models/sale_order.py`).
- **Cambio de comportamiento real** para cualquier cliente VE con
  `account_use_credit_limit=True` y `not_allow_sell_products=False`: el
  chequeo de crédito en presupuestos, que hoy nunca corre, empieza a correr.
  Requiere aviso explícito a Producto antes de mergear — no es un cambio
  cosmético.
- Sin cambios de modelo, vista ni seguridad.
- Manifest: bump de versión pendiente de definir junto con el ID de ticket.
