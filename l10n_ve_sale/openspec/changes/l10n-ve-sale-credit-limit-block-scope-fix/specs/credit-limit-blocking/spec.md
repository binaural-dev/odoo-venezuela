## ADDED Requirements

### Requirement: El límite de crédito se valida en toda confirmación de presupuesto

Cuando `company.account_use_credit_limit` y
`partner.use_partner_credit_limit_order` están activos,
`sale.order.action_confirm()` SHALL bloquear la confirmación de cualquier
presupuesto cuya deuda total proyectada (`partner.credit +
order.amount_total`) supere `partner.credit_limit`, lanzando
`ValidationError`.

Esta validación SHALL ejecutarse independientemente del valor de
`company.not_allow_sell_products` — esa opción gobierna únicamente la
validación de disponibilidad de stock y no debe condicionar el chequeo de
crédito.

Un contexto con `skip_credit_limit_check=True` SHALL saltear esta
validación por completo, para flujos con autorización explícita.

#### Scenario: Bloqueo con la configuración estándar de compañía
- **GIVEN** una compañía con `account_use_credit_limit=True` y
  `not_allow_sell_products=False` (configuración por defecto)
- **AND** un cliente con `use_partner_credit_limit_order=True` cuya deuda
  más el presupuesto supera su límite
- **WHEN** se confirma el presupuesto
- **THEN** se lanza `ValidationError` y el presupuesto no se confirma

#### Scenario: La validación de stock no afecta al chequeo de crédito
- **GIVEN** la misma compañía y cliente del escenario anterior, con
  `not_allow_sell_products` en `True` o en `False`
- **THEN** el resultado del chequeo de crédito es el mismo en ambos casos

#### Scenario: Bypass explícito
- **GIVEN** un cliente sobre su límite de crédito
- **WHEN** se confirma el presupuesto con `skip_credit_limit_check=True` en
  el contexto
- **THEN** el presupuesto se confirma sin lanzar `ValidationError`

#### Scenario: Compañía sin el gate activo
- **GIVEN** `company.account_use_credit_limit=False`
- **THEN** el presupuesto se confirma sin ninguna validación de crédito, sin
  importar el monto o el límite del cliente

## Implementation

| Component | Path |
|---|---|
| Modelo | `l10n_ve_sale/models/sale_order.py` |
| Tests | `l10n_ve_sale/tests/test_action_confirm.py` |

## Notes

- Antes de este cambio, el bloque de crédito estaba anidado dentro de `if
  company.not_allow_sell_products`, por lo que nunca se ejecutaba con la
  configuración por defecto de compañía (`not_allow_sell_products=False`).
- No hay conversión de moneda en esta comparación — `credit`/`credit_limit`
  están en moneda de la compañía, `order.amount_total` en la moneda del
  pedido. La versión currency-aware es responsabilidad de
  `integra-addons/binaural_credit_limit`, que consume `action_confirm` una
  vez corregido su alcance.
