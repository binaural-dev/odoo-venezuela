## Why

En `l10n_ve_pos_mf`, cerrar sesión de PDV exige hoy, para todo usuario, pasar
por el flujo dual fiscal (Reporte X + Reporte Z obligatorio, con bloqueo si
hay pedidos sin facturar en la máquina fiscal). No existe forma de que un
usuario autorizado (ej. gerente, soporte) cierre una sesión con el botón
nativo de Odoo cuando la situación lo amerite (correcciones, sesiones sin
máquina fiscal), sin quitarle a nadie el flujo fiscal existente.

## What Changes

- Nuevo grupo de seguridad `l10n_ve_pos_mf.group_pos_close_native` ("Close
  POS session natively (skip mandatory Z report)"), checkbox independiente
  en "Extra Rights" (sin `privilege_id`).
- Nuevo `models/res_users.py` que expone `_can_close_session_native` al
  frontend del PDV vía `_load_pos_data_read` (mismo patrón que
  `l10n_ve_pos/models/res_users.py`).
- `ClosePosPopup.js`/`ClosePosPopup.xml`: se añade un tercer botón "Cerrar
  sesión", visible solo con el grupo, junto a los dos botones existentes
  (Reporte X, Cerrar sesion e imprimir Z) — no los reemplaza.
- El botón nuevo es un bypass total (llama a `confirm()` nativo): no imprime
  Reporte Z, no incrementa `report_z`/`mf_reportz`, y no valida pedidos sin
  facturar (`_getUnfiscalizedOrders`). Decisión deliberada, confirmada con el
  usuario.
- Sin el grupo, el comportamiento no cambia: solo se ven los dos botones del
  flujo dual, igual que hoy. Nadie tiene el grupo asignado por defecto.
- Traducción es_VE del nombre del grupo añadida en `i18n/es_VE.po`.

## Capabilities

### New Capabilities
- `pos-close-session-permission`: control de acceso por grupo a un cierre de
  sesión de PDV nativo (sin Reporte Z) como alternativa opcional al flujo
  fiscal dual existente.

### Modified Capabilities
(ninguna — el flujo dual existente no tiene spec propio documentado hasta
ahora y no cambia su comportamiento)

## Impact

- Módulo: `l10n_ve_pos_mf` (seguridad, modelos, frontend PDV, i18n). No se
  toca `l10n_ve_pos` ni ningún otro módulo — solo se sigue su patrón de
  permisos existente (`group_change_qty_on_pos_order` /
  `group_change_price_on_pos_order`).
- Riesgo fiscal: un usuario con el nuevo grupo puede cerrar una sesión con
  ventas sin fiscalizar en la máquina fiscal. El grupo debe asignarse con
  criterio, no de forma general.
- Verificación: manual en navegador (ver `tasks.md`); no se ejecutaron tests
  automatizados ni `odoo -u` como parte de este cambio.
- Referencia: tarea https://binaural.odoo.com/odoo/action-341/78328
