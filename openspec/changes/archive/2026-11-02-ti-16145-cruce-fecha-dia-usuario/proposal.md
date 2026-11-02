## Why

Ticket https://www.binauraldev.com/odoo/helpdesk/58/tickets/16145 (referencia #16183): en Nova, al
cerrar la caja de noche (sesión `AV. VICTORIA/00029`, viernes 30/10/2026 a las 9:35 pm) sale
"No hay una tasa asignada para USD al 2026-10-31, configúrela." y la sesión no cierra, aunque en
Venezuela todavía era 30 y la tasa del 30 estaba cargada.

Es un camino que no cubrió el ticket 16058 ("Pedido de tasa de cambio del día siguiente",
change archivado `2026-10-27-fecha-tasa-zona-horaria-usuario`). Aquel fix hace que `compute_rate`
convierta a la fecha del usuario cuando recibe un Datetime, pero el asiento de cruce le llega ya
como fecha UTC:

1. Al pasar a "Control de cierre", el core guarda `stop_at = now()`, en UTC: las 9:30 pm de
   Caracas son `2026-10-31 01:30`.
2. Al cerrar, `pos.session._validate_cross_move` crea el cruce de los métodos en divisa con
   `date=session.stop_at` (método sin "Identificar cliente") o `date=payment.create_date` (con
   "Identificar cliente"), los dos Datetime en UTC.
3. `account.move.date` es un campo Date: el ORM convierte el Datetime con `.date()` y el asiento
   queda del día UTC, el 31.
4. `l10n_ve_accountant` busca, al crear el asiento, la tasa exacta de `move.date`; la del 31 no
   existe y lanza `UserError`.

Reintentar al día siguiente no sirve, porque `stop_at` ya quedó guardado. Si la tasa del día
siguiente existiera, el cierre pasaría pero el cruce quedaría con la fecha contable equivocada.

## What Changes

- `pos.session._create_cross_move`: si `date` es un Datetime, lo pasa al día del usuario con
  `fields.Date.context_today(self, date)` antes de crear el asiento, igual que el core fecha sus
  asientos de pago (`fields.Date.context_today(self, timestamp=payment.payment_date)`). Una fecha
  (`date`) pasa sin cambios.
- Se corrige en el punto por el que pasan todos los cruces, y no en cada llamador: cubre las dos
  granularidades de `_validate_cross_move` y también las de `binaural_pos_multicurrency`
  (`_validate_cross_move_in_session_currency`, que llama a `_create_cross_move_for` con los mismos
  `stop_at` / `create_date`) sin tocar integra-addons. Los llamadores de `binaural_pos_close`
  (entrada/salida de efectivo y diferencias de apertura y cierre) ya pasan fechas.

## Impact

- **Módulo tocado:** `l10n_ve_pos` (19.0.1.28.1 → 19.0.1.28.2).
- **Despliegue:** `-u l10n_ve_pos` no es necesario (solo Python); basta reiniciar el servicio.
  Una sesión que quedó trabada en "Control de cierre" cierra después del despliegue con el cruce
  en el día local de su `stop_at`.
- **Zona horaria:** se usa la del usuario que cierra (`tz` del contexto o del usuario), como el
  resto de la localización desde el ticket 16058. Un usuario sin zona horaria sigue en UTC.
- **Fuera de alcance:** cargar la tasa automáticamente para fines de semana o feriados.
