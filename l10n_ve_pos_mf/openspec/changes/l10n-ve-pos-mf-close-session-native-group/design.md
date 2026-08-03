## Context

El popup de cierre de sesión del PDV (`ClosePosPopup`) ya fue modificado por
`l10n_ve_pos_mf` para exigir un flujo fiscal dual (Reporte X + Reporte Z
obligatorio) a todo usuario, reemplazando el botón nativo `Close Register`
del core de Odoo 19 vía herencia XML (`t-inherit-mode="extension"`, xpath
`position="replace"` sobre `//button[@t-on-click='confirm']`). El módulo
hermano `l10n_ve_pos` (dependencia de `l10n_ve_pos_mf`) ya resuelve un
problema análogo — exponer un permiso custom de VE al frontend del PDV — con
`group_change_qty_on_pos_order` / `group_change_price_on_pos_order`
(`res.groups` sin `privilege_id`, expuestos vía `_load_pos_data_read` con
clave `_`). Este cambio reutiliza ese mismo patrón para un permiso nuevo.

## Goals / Non-Goals

**Goals:**
- Permitir que usuarios seleccionados cierren sesión de PDV con el botón
  nativo de Odoo (sin Reporte Z), cuando la situación lo amerite.
- No alterar el comportamiento de nadie que no tenga el grupo.

**Non-Goals:**
- No se rediseña el flujo fiscal dual existente (Reporte X / Reporte Z).
- No se agrega UI de configuración nueva (el control de acceso es 100% vía
  grupo de seguridad estándar de Odoo, en "Extra Rights").
- No se restringe también el Reporte X para el nuevo grupo — ese botón de
  consulta sigue disponible para todos, como hoy.

## Decisions

- **Aditivo, no toggle/reemplazo:** el botón nativo se agrega como tercera
  opción junto a los dos existentes, en vez de mostrar unos u otros según el
  grupo. Alternativa considerada y descartada: `t-if`/`t-else` que
  reemplazara el flujo dual por el nativo para el grupo — el usuario indicó
  explícitamente que quiere las tres opciones visibles a la vez para poder
  elegir en el momento del cierre.
- **Bypass total, no parcial:** el botón nativo llama a `confirm()` directo,
  sin ejecutar `_getUnfiscalizedOrders()` ni exigir Reporte Z. Alternativa
  considerada: mantener la validación de pedidos sin facturar y solo saltar
  el Reporte Z. Se descartó porque el usuario confirmó que quiere el
  comportamiento 100% nativo de Odoo para este botón, asumiendo el riesgo
  fiscal como decisión deliberada (grupo de asignación restringida).
- **`res.groups` sin `privilege_id`:** igual que los dos grupos VE ya
  existentes en `l10n_ve_pos`, para que aparezca como checkbox independiente
  en "Extra Rights" en vez de fusionarse (radio/select) con
  `group_pos_user`/`group_pos_manager`.
- **Exposición vía `_load_pos_data_read` con prefijo `_`:** único formato
  que el `related_models` del cliente conserva sin descartar en Odoo 19 (ver
  capability `pos-close-session-permission` / spec.md, y memoria
  `pos-o19-related-models-underscore-fields`).
- **Botón nuevo colocado después del de Reporte Z** (`position="after"` en
  el xpath), no antes del de Reporte X, para que el orden visual sea:
  Reporte X → Cerrar sesion e imprimir Z → Cerrar sesión (nativo), dejando
  la opción de bypass fiscal al final.

## Risks / Trade-offs

- [Riesgo] Un usuario con el grupo puede cerrar una sesión con ventas sin
  fiscalizar en la máquina fiscal, sin ninguna advertencia adicional más
  allá del tooltip del botón → Mitigación: el grupo es opt-in explícito (no
  se asigna a nadie por defecto) y debe reservarse a roles de
  gerencia/soporte; el tooltip dice explícitamente que se salta Reporte Z y
  la validación de pedidos.
- [Riesgo] Confusión del cajero entre los tres botones → Mitigación: el
  tercer botón solo aparece para quien tenga el grupo (la mayoría de
  cajeros no lo verá) y usa una etiqueta distinta ("Cerrar sesión" vs
  "Cerrar sesion e imprimir Z").
