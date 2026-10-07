## MODIFIED Requirements

### Requirement: Corrección de `payment_state` cuando una ND/NC cierra una factura sin pago real de por medio

El sistema SHALL corregir el `payment_state` nativo de Odoo a `'paid'` cuando
una factura de cliente queda TOTALMENTE cerrada (residual cero) por una
combinación de documentos donde NINGUNO es un `account.payment`/línea de
extracto real, pero AL MENOS UNO es una ND/NC de este módulo -- el caso
concreto es el "cruce de anticipo" de `l10n_ve_igtf`
(`_reconcile_move_with_payment_difference`, un `account.move` armado a mano,
`move_type='entry'`, sin `origin_payment_id`) cuando ese cruce deja además un
residual de diferencial cambiario.

Sin esta corrección, el cálculo nativo de Odoo
(`account.move._compute_payment_state`) clasifica ese caso como
`payment_state = 'reversed'` -- exclusivo a este módulo: SIN él, ese mismo
escenario (anticipo + diferencial) siempre resolvía a `'paid'`, porque el
asiento genérico nativo que Odoo genera por defecto también es
`move_type='entry'` (nunca introduce `'out_refund'` en la combinación de
tipos que el núcleo evalúa). Al reemplazar ese asiento genérico por una NC
fiscal real (`out_refund`, el propósito de este módulo), esa NC pasa a ser la
pieza que sí introduce `'out_refund'` en la combinación, y el núcleo concluye
erróneamente que la factura fue "revertida" en vez de pagada.

La corrección SHALL re-evaluar la MISMA comparación de `move_type` que usa el
núcleo, pero excluyendo del conjunto los documentos que sean, a la vez,
`l10n_ve_exchange_diff_entry=True` Y de un `move_type` que este módulo
realmente emite (`out_invoice`/`out_refund`) -- NUNCA solo por el flag: ese
mismo flag también marca (para trazabilidad) el asiento genérico nativo de
Odoo, que es legítimo dejar en el cómputo normal. Si al excluir las notas
propias la combinación restante YA NO arma una reversión, corrige a
`'paid'` -- el valor por defecto que el propio núcleo ya usa en esa rama
antes de evaluar la condición de reversión. Si la combinación restante SIGUE
armando una reversión (ej. una Nota de Crédito de NEGOCIO real, no
relacionada, que también participó en cerrar la factura), NO SHALL corregir
nada -- esa clasificación es genuina.

Si al excluir las notas propias NO queda NINGUNA otra contraparte
(`remaining_types` vacío -- por ejemplo, tras desconciliar el cruce de
anticipo que originalmente acompañaba a la nota, dejándola como la ÚNICA
pieza de la conciliación), la corrección NO SHALL forzar `'paid'`: una nota
propia sola como contraparte es EXACTAMENTE la definición nativa de
`'reversed'` del núcleo (un solo `out_refund`), así que el valor que el
núcleo ya calculó es correcto y forzar `'paid'` ahí lo sobrescribiría con un
valor desactualizado.

Un documento marcado con `l10n_ve_exchange_diff_entry=True` cuyo `move_type`
NO sea ni `'entry'` (asiento genérico) ni `out_invoice`/`out_refund` (nota
propia) SHALL abortar con `UserError` explícito en vez de ignorarse en
silencio -- ese flag no tiene ningún otro uso legítimo en el módulo, así que
verlo en cualquier otro tipo de documento indica un estado inconsistente que
podría corromper este mismo cómputo más adelante de forma mucho más difícil
de diagnosticar.

Esta corrección NO SHALL requerir `.sudo()`: el escenario real que corrige
(factura + cruce de anticipo + nota propia) siempre ocurre dentro de la
MISMA compañía -- `_create_exchange_difference_note` ya fuerza que la nota
sea de `invoice.company_id`. Si algún día una contraparte de otra compañía
(sucursal/matriz, fuera de alcance) no es visible para el usuario/proceso
actual, SHALL fallar con `AccessError` en vez de completar el flujo en
silencio.

#### Scenario: Factura cerrada por anticipo + NC de diferencial no queda "revertida"

- **GIVEN** una factura de cliente en USD
- **AND** se cierra vía el cruce de anticipo de `l10n_ve_igtf` (`entry`, sin `origin_payment_id`)
- **AND** ese cruce deja un residual de pérdida cambiaria, documentado con la NC de este módulo
- **WHEN** se recomputa `payment_state` de la factura
- **THEN** queda `'paid'`, no `'reversed'`

#### Scenario: Una reversión genuina, no relacionada, no se corrige

- **GIVEN** una factura cerrada por una combinación que incluye una Nota de Crédito de NEGOCIO real (no de este módulo) además de una nota propia de una conciliación anterior no relacionada
- **WHEN** se recomputa `payment_state`
- **AND** excluir la nota propia de la combinación NO cambia el resultado (la NC de negocio por sí sola ya arma la reversión)
- **THEN** `payment_state` se queda en `'reversed'`

#### Scenario: La nota propia queda sola tras desconciliar el resto -- no se fuerza 'paid'

- **GIVEN** una factura cuya conciliación incluía un cruce de anticipo y su NC de diferencial
- **AND** el cruce de anticipo se desconcilia, dejando la NC como la ÚNICA contraparte restante
- **WHEN** se recomputa `payment_state`
- **THEN** el sistema NO fuerza `'paid'` -- se respeta el `'reversed'` que el núcleo ya calculó, correcto para una sola nota de crédito como contraparte

#### Scenario: Documento con el flag en un `move_type` inesperado aborta

- **GIVEN** un documento con `l10n_ve_exchange_diff_entry=True` cuyo `move_type` no es `'entry'`, `'out_invoice'` ni `'out_refund'`
- **WHEN** participa en el cómputo de `payment_state` de una factura marcada `'reversed'`
- **THEN** se lanza `UserError` explícito en vez de ignorarlo en silencio
