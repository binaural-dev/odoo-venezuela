# Fix: no se pueden registrar pagos con fecha futura

## Why

Ticket Helpdesk #15682 (https://binaural.odoo.com/odoo/my-tickets/15682).
Un pago podía registrarse con fecha posterior a hoy, tanto desde el formulario de pagos como desde el
asistente de registrar pago, con las mismas consecuencias que las facturas con fecha futura (secuencias,
tasas desconocidas). Es la tercera validación de fechas junto a 15450 (documentos con fecha futura) y
15594 (fechas de NC/ND respecto a su origen).

## What Changes

- `account.payment` (`models/account_payment.py`): constraint de guardado `_check_date_not_in_future`;
  `date` no puede ser posterior a `fields.Date.context_today` (zona horaria del usuario), al crear ni al
  escribir.
- `account.payment.register` (`wizard/account_payment_register.py`): constraint
  `_check_payment_date_not_in_future` sobre `payment_date`, para rechazarlo en el asistente antes de crear
  ningún pago.
- Traducción `es_VE` del mensaje y bump `19.0.1.0.29` -> `19.0.1.0.30`.

## Decisiones

- Todo vive en `l10n_ve_accountant`, que es quien maneja la parte contable.
- Es una constraint de guardado y no un guard en `action_post`: el ticket pide impedir el registro del pago
  desde el formulario y el asistente, no solo su confirmación.
- Se usa `context_today`, nunca `Date.today()`, para no depender de la hora del servidor (UTC).

## Non-goals

- No toca las reglas de 15450 ni de 15594 (facturas y notas).
- Este change es independiente de la rama `maint-19.0-fix-ti-15450-block-future-dated-documents`. Si esa
  rama se mergea, su test `test_exchange_difference_note_with_future_payment_date_is_posted`
  (`l10n_ve_exchange_difference`), que crea un pago con fecha de mañana, ya no podrá crear el pago y debe
  quitarse o adaptarse; la exención `l10n_ve_skip_future_date_check` de las notas de diferencial sigue
  siendo válida como defensa.
