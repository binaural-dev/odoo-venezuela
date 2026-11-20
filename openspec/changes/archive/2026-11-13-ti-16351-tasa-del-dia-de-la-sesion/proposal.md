## Why

Ticket https://www.binauraldev.com/odoo/helpdesk/58/tickets/16351 (referencia #16389). Antecedente: ticket
16201 (#16239, Grupo Nova): la orden 000339 de la caja 1 Av. Victoria del 03/11/2026 se facturó con la tasa
del 02/11 aunque la del 03/11 estaba cargada (Pirulin 4,09 $ salió en 3.642,66 Bs en vez de 3.644,62 Bs).

Regla del negocio (Jesús Cegarra, 2026-11-12): una sesión trabaja SIEMPRE con la tasa de su apertura, pero
una sesión del día 3 no puede arrancar con la tasa del día 2.

Hoy la sesión no guarda su tasa. `pos.config.foreign_rate` se calcula con la fecha de hoy cada vez que el PdV
carga los datos, y después vive en el navegador (IndexedDB). Casos que lo rompen:

1. **Apertura sin recargar.** El popup de apertura confirma la sesión (`set_opening_control`, `start_at = now`)
   sin recargar los datos: una caja cargada la noche anterior abre al día siguiente con la tasa de ayer. Es el
   caso de Nova.
2. **Sesión que pasa la medianoche.** Sigue vendiendo con la tasa del día anterior (correcto según la regla),
   pero si al día siguiente se recarga (entrar desde el backend, "Volver a cargar datos") toma la tasa nueva y
   la sesión mezcla dos tasas.
3. **Moneda vieja en una caja en Bs.** El core pasa la lista de precios en divisa a la moneda de la caja con el
   `rate` de `res.currency`, que se carga incremental por `write_date`. Una tasa nueva no cambia el
   `write_date` de la moneda: una sesión nueva convierte los precios con la tasa de la última carga completa
   mientras los montos en divisa usan la de `pos.config`. `binaural_pos_multicurrency` ya lo evitaba solo en
   las cajas en otra moneda.
4. **Apertura sin tasa del día.** La caja abre con tasa 0 y ninguna orden sincroniza ("No hay una tasa
   asignada…").
5. **Otra pestaña o equipo** de la misma caja con datos viejos.

## What Changes

- `pos.session.foreign_rate_date` (nuevo, Date): el día de la tasa de la sesión, el de su apertura. Se fija en
  `_set_opening_control_data`, por donde pasan la caja y el kiosko.
- Sin tasa del día la sesión no abre (`UserError` en el servidor y aviso "Sin tasa del día" en el popup).
- `pos.session._get_rate_date()` y `pos.config._get_pos_rate_date()`: el día de la tasa (el de la sesión o, sin
  sesión abierta, el del usuario). `pos.config._compute_rate` busca la tasa de ese día (con la compañía de la
  caja). Todo lo que lee la tasa de la caja (carga del PdV, `_convert`, órdenes del kiosko, asiento del
  cierre) usa la del día de la sesión, también después de medianoche. Los módulos que convierten con la tasa
  nativa de Odoo usan el helper: en integra-addons, `binaural_pos_multicurrency` (cajas en otra moneda) y
  `binaural_pos_close` (cajón en divisa), en el PR complementario.
- Se fija el **día**, no el valor: una corrección de la tasa de ese mismo día entra al recargar los datos
  (decisión de Jesús Cegarra, 2026-11-12), como ya hacen las cajas en Bs y `binaural_pos_multicurrency`.
- `res.currency`: llega completa en cada carga (sin el filtro por `write_date`) y con el `rate` del día de la
  sesión; la moneda alterna, con la tasa exacta de la caja. El kiosko (`l10n_ve_pos_self_order`) lee las
  monedas por otra vía (`_load_pos_self_data_read`) y recibe la misma tasa.
- `pos.session.check_opening_rate`: antes de confirmar la apertura el PdV manda las tasas que tiene cargadas
  (la de la caja y el `rate` de cada moneda). Si no son las de la sesión, el popup muestra "Tasa
  desactualizada" y recarga los datos completos (`reloadData(true)`) en vez de abrir. Si el equipo tiene órdenes
  pagadas sin enviar (solo se envían con la sesión abierta y una recarga las perdería), abre la sesión y
  recarga enseguida. Lo que otros módulos registran al abrir va en el gancho `_beforeOpeningSession` del popup,
  después del chequeo (`binaural_pos_close` registra ahí el cajón en divisa).
- Después de abrir, el popup lee `foreign_rate_date` de la sesión: el popup del core no recarga los datos y,
  sin el día, el aviso de sesión de un día anterior no saldría en el equipo que la abrió.
- Al cerrar una sesión que pasó la medianoche, el asiento de la sesión (`_create_account_move`) y los pagos
  bancarios combinados toman la tasa de la caja, que ahora es la del día de la sesión (antes, la del día del
  cierre): la misma con la que se vendió.
- Sesión de un día anterior: se respeta su tasa y solo se avisa ("Sesión de un día anterior") al cargar el PdV
  y como notificación al cobrar, sin bloquear.

## Non-goals y limitaciones

- No se bloquea una sesión que pasa la medianoche: decisión del usuario, solo se avisa.
- **Kiosko abierto varios días:** factura con la tasa del día de su apertura sin aviso (el kiosko no usa
  `PosStore`). Queda declarado; cerrar el kiosko a diario.
- **Medianoche entre el chequeo y la apertura:** el popup llama a `check_opening_rate` y luego a
  `set_opening_control`; si el día cambia entre las dos llamadas (milisegundos), la sesión queda con el día
  nuevo y el navegador con la tasa anterior hasta recargar. Decisión del usuario (2026-11-12): limitación.
- **Usuario sin zona horaria:** cae en UTC; si abre entre las 20:00 y las 24:00 de Caracas, la sesión queda
  con el día siguiente (o no abre sin esa tasa). Viene de antes; ahora dura toda la sesión.
- **Reloj del navegador:** el aviso de sesión de un día anterior compara con la fecha del equipo.
- **Sincronización:** no se valida la tasa de la orden al sincronizar (rechazarla dejaría órdenes ya impresas
  en la máquina fiscal sin enviar). Una pestaña o equipo con datos viejos se corrige al abrir, no después.

## Impact

- **Módulo tocado:** `l10n_ve_pos` (19.0.1.28.2 → 19.0.1.29.0).
- **Despliegue:** `-u l10n_ve_pos` (columna nueva en `pos_session`). Las sesiones abiertas antes del update no
  tienen día guardado: siguen con la tasa del día del usuario hasta cerrarse.
- **Kiosko:** sin tasa del día no abre (`action_open_wizard` muestra el error). `l10n_ve_pos_self_order`
  19.0.1.7.1 → 19.0.1.8.0 (su OpenSpec propio: `l10n_ve_pos_self_order/openspec/changes/ti-16351-…`).
- **Sesiones abiertas varios días** (farmacias 24 h, kioskos): antes tomaban la tasa del día al recargar;
  ahora trabajan con la del día de su apertura hasta cerrarse. Avisar a soporte y a los clientes.
- **Orden de merge:** este PR primero; el de integra-addons usa `_get_pos_rate_date` / `_get_rate_date` y el
  gancho `_beforeOpeningSession`.
- **Tercera moneda (tarea 86066, ya en 19.0):** `tender_currency_rates` también usa el día de la sesión y el
  chequeo de apertura compara las tasas de cobro; en integra-addons la apertura de los cajones en tercera moneda
  pasa al gancho `_beforeOpeningSession`.
