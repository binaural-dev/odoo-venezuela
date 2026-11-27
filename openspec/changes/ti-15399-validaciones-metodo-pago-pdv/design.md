## Context

El método de pago del PdV tiene dos diarios propios de la localización además del diario del core: el diario
afectado de banco o efectivo (`cross_journal`, la caja real) y el diario de la cuenta de cruce
(`cross_account_journal`). Al cerrar la sesión, un método en moneda alterna o con moneda de cobro cruza lo cobrado
de su diario al diario afectado. En efectivo, el cruce va de la transitoria del diario a la del diario afectado
(`pos.session._cross_move_uses_suspense`).

## D1. La caja no es obligatoria en el método

El core crea métodos sin caja al crear un punto de venta y desde los ajustes del PdV. Exigir la caja rompería esos
flujos. Un método sin caja se valida cuando se le asigna una: desde el método (regla nueva) o desde la caja (core).

## D2. La regla de las transitorias también se revisa en el diario

La cuenta transitoria no se edita en el método sino en el diario. Una regla solo en el método dejaría pasar el
caso más común: el método se configura bien y después alguien cambia la transitoria del diario. Por eso
`account.journal` revisa, al cambiar `suspense_account_id`, todos los métodos que usan el diario como diario o
como diario afectado (con `sudo()` y también los archivados, que no se revalidan al reactivarse).

La regla aplica a todo método en moneda alterna o con moneda de cobro, como pide el ticket, aunque el cruce de un
método de banco no use las transitorias (va de `outstanding_account_id` a la cuenta del diario afectado).
Alternativa: limitarla a los métodos de efectivo, donde el cruce sí usa las transitorias. Se mantiene la regla del
ticket, más simple de explicar al configurar. Si la revisión prefiere limitarla, el cambio es filtrar por
`type == "cash"` en `_check_distinct_suspense_accounts`.

## D3. Sin regla de moneda para un método sin caja

El parche original exigía que el diario de un método en moneda alterna o con moneda de cobro estuviera en la
moneda de la compañía, aunque el método no tuviera caja. Se quita, por tres razones:

- **Rompe configuraciones válidas.** `binaural_pos_multicurrency` permite un método con moneda de cobro (p. ej.
  EUR) en una caja en USD, con su diario transitorio en USD (`pos.config._get_tender_currency_error`). La regla lo
  rechazaba.
- **Contradice la spec.** El requirement «La línea transitoria del cruce en la moneda del diario del método»
  cubre un método con el diario en la alterna.
- **Rompe la suite.** Con el parche original, 17 clases de prueba de `l10n_ve_pos` fallan en `setUpClass`: sus
  fixtures crean métodos en moneda alterna con el diario en la moneda de la caja alterna (`sales_in_foreign`).

No hace falta: en cuanto el método tiene caja, la regla de moneda del ticket (diario en la moneda de cada caja)
ya obliga a lo correcto, y un método en moneda alterna en una caja que no es de la moneda de la compañía lo rechaza
`binaural_pos_multicurrency`.

## D4. Lo ya guardado no se revalida

Un `@api.constrains` solo corre al escribir los campos que vigila. No se agrega migración: revalidar en la
actualización bloquearía el `-u` de clientes con la configuración por defecto de Odoo. Los métodos ya guardados
con las dos transitorias iguales se encuentran con:

```sql
SELECT m.id, m.name, j.name AS diario, cj.name AS diario_afectado, j.suspense_account_id
FROM pos_payment_method m
JOIN account_journal j ON j.id = m.journal_id
JOIN account_journal cj ON cj.id = m.cross_journal
WHERE (m.is_foreign_currency OR m.tender_currency_id IS NOT NULL)
  AND j.suspense_account_id IS NOT NULL
  AND j.suspense_account_id = cj.suspense_account_id;
```

Mientras no se editen, su cruce sigue creándose sin efecto contable, como dice el change
`cruce-venta-efectivo-entre-transitorias`.
