## 1. Diagnóstico

- [x] 1.1 Confirmado leyendo el código real (no memoria) que el bloque de
      crédito está anidado dentro de `if
      self.env.company.not_allow_sell_products` en
      `l10n_ve_sale/models/sale_order.py`.
- [x] 1.2 Confirmado que `not_allow_sell_products` es `False` por default
      (`l10n_ve_sale/models/res_company.py`).
- [x] 1.3 Confirmado que no existe ningún test que cubra el chequeo de
      crédito en `l10n_ve_sale` (`grep -rn "credit_limit"
      l10n_ve_sale/tests/` vacío).
- [x] 1.4 Confirmado que `l10n_ve_accountant.action_post` sí es
      independiente y sí soporta `skip_credit_limit_check`.

## 2. Fix

- [x] 2.1 Sacar el bloque de crédito de adentro del `if
      not_allow_sell_products`, como `if` hermano en el mismo `for order`.
- [x] 2.2 Agregar `skip_credit_limit_check = self.env.context.get(
      "skip_credit_limit_check", False)` y usarlo como primer gate del
      bloque.
- [x] 2.3 Bump de versión del manifest (`19.0.1.0.6` → `19.0.1.0.7`).

## 3. Verificación

- [ ] 3.1 Confirmar un presupuesto con `not_allow_sell_products=False`,
      `account_use_credit_limit=True`, `use_partner_credit_limit_order=True`
      y el cliente sobre el límite → antes del fix pasa (bug), después se
      bloquea con `ValidationError`.
- [ ] 3.2 Confirmar el mismo caso con `not_allow_sell_products=True` → se
      comporta igual antes y después del fix (no regresión del caso que sí
      funcionaba).
- [ ] 3.3 Confirmar con `skip_credit_limit_check=True` en el contexto → no
      bloquea, sin importar el resto de los gates.
- [ ] 3.4 Confirmar que la validación de stock (`not_allow_sell_products`)
      no cambia de comportamiento en ningún escenario.
- [ ] 3.5 Agregar los tests automatizados descritos en
      `specs/credit-limit-blocking/spec.md`.

## 4. Pendiente de Producto

- [ ] 4.1 Aviso explícito a Producto: este fix cambia comportamiento real
      para clientes VE con crédito activo y `not_allow_sell_products`
      desactivado. Sign-off requerido antes de mergear.
- [x] 4.2 Asociado a TA-81707 y rama creada:
      `19.0-fix-ta-81707-l10n-ve-sale-credit-limit-scope`.

## 5. OpenSpec

- [x] `proposal.md` + `design.md` + `tasks.md`
- [x] Spec delta — `credit-limit-blocking` (ADDED)
- [ ] `openspec validate --changes`
