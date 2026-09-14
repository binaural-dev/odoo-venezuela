## Context

`l10n_ve_sale.action_confirm()` reescribe el `action_confirm` nativo de
`sale.order` para dos validaciones propias de la localización venezolana:
disponibilidad de stock (gateada por `not_allow_sell_products`) y límite de
crédito (gateada por `account_use_credit_limit` +
`use_partner_credit_limit_order`). Las dos viven en el mismo método, y la
segunda quedó anidada dentro del `if` de la primera en algún punto de su
historia — no hay ningún commit que documente la intención de acoplarlas.

## Goals / Non-Goals

**Goals:**
- Que el chequeo de crédito en `action_confirm` corra siempre que sus
  propios gates lo indiquen, sin depender de una opción de stock sin
  relación.
- Dar un mecanismo de bypass explícito y nombrado igual al que ya existe en
  `l10n_ve_accountant`, para consistencia entre los dos puntos de chequeo
  del producto.

**Non-Goals:**
- No se resuelve aquí la falta de conversión de moneda en la comparación —
  eso es explícitamente el trabajo de `integra-addons/binaural_credit_limit`,
  que depende de este fix.
- No se audita el resto del módulo en busca de acoplamientos similares.

## Decisions

- **Sacar el bloque de crédito del `if`, no envolver el `if` en una
  condición más grande.** La opción más simple y la que menos superficie de
  cambio introduce: el bloque de crédito pasa a ser un `if` hermano al de
  stock, ambos dentro del mismo `for order in self:`.
- **Nombrar el flag `skip_credit_limit_check`, no uno nuevo.** Ya existe ese
  nombre exacto en `l10n_ve_accountant._is_subject_to_credit_limit()` con la
  misma semántica (bypass explícito, nunca activado por defecto) — reusar el
  nombre evita que quien integra ambos módulos tenga que aprender dos flags
  para el mismo concepto.
- **No fusionar `skip_credit_limit_check` con
  `skip_not_allow_sell_products_validation`.** Son conceptos distintos; un
  flujo que necesita saltar el chequeo de crédito (una orden ya aprobada
  manualmente, por ejemplo) no debería tener que saltar también la
  validación de stock como efecto colateral.

## Risks / Trade-offs

- **Este es un cambio de comportamiento real, no un refactor.** Cualquier
  compañía VE con `account_use_credit_limit=True` y
  `not_allow_sell_products=False` (la config por defecto) empezará a
  bloquear presupuestos que hoy pasan sin aviso. Requiere sign-off de
  Producto antes de mergear, con aviso explícito de que este es un fix de un
  bug preexistente y no parte de la feature de moneda alterna en curso.
- Sin test de regresión previo a este cambio — el que se agrega en este
  mismo proposal es la primera cobertura que existe para este chequeo.

## Migration Plan

Sin migración de datos — es lógica de validación en memoria, no hay campos
ni tablas involucradas. Requiere comunicar el cambio de comportamiento a los
clientes VE con crédito activo antes del release (ver Risks).
