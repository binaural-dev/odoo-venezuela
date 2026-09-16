# Tasks

## 1. Fix (bug 1: `groups_id` no llega al frontend)

- [x] 1.1 `models/res_users.py`: override `_load_pos_data_read` inyectando
      `can_change_qty_on_pos_order` / `can_change_price_on_pos_order` vía
      `has_group()`
- [x] 1.2 Registrar `res_users` en `models/__init__.py`
- [x] 1.3 `product_screen.js`: leer los dos booleanos nuevos en vez de
      `this.pos.user.groups_id` (inexistente en Odoo 19)

## 2. Fix (bug 2: `privilege_id` hace los grupos excluyentes entre sí y con el acceso base)

- [x] 2.1 `security/res_group.xml`: `privilege_id` → `eval="False"` en
      ambos grupos, para que dejen de compartir el dropdown exclusivo con
      `group_pos_user`/`group_pos_manager` y pasen a checkboxes
      independientes en "Extra Rights"

## 3. Verificación en producción (BD `pos`, contenedor `proj`)

- [x] 3.1 `-u l10n_ve_pos` corrido (confirmado: `privilege_id` de ambos
      grupos en NULL en `res_groups`, módulo en estado `installed`)
- [x] 3.2 Usuario "Soporte Binaural" (`res.users` id 2, = `admin`, ya en
      `group_pos_manager` — no perdió el acceso base) confirmado en ambos
      grupos custom (`res_groups_users_rel`)
- [x] 3.3 `odoo shell` de solo lectura: `has_group()` → `True` en ambos;
      `manual_discount=False` explica el bloqueo de `%` (config, no bug);
      `restrict_price_control=False` y `_role='manager'` descartados como
      causa de Precio
- [x] 3.4 Sin shadowing de módulo: `l10n_ve_pos` no existe al nivel raíz de
      `src/custom/19-homologacion-jul-2026-pos` (anidado 2 niveles, Odoo no
      lo descubre) — confirmado de nuevo para este fix
- [x] 3.5 JS servido en vivo coincide con el archivo en disco (`curl`
      directo al contenedor)
- [x] 3.6 Log temporal en `_load_pos_data_read` confirmó que la RPC real
      del navegador (`pos.session/load_data`) manda
      `can_change_qty_on_pos_order=True` — descarta problema de caché de
      datos (IndexedDB) una vez limpiado el storage del sitio
- [x] 3.7 Debug visual en el propio texto del botón reveló `undefined` del
      lado cliente pese al RPC correcto → encontrado bug 3
      (`related_models` descarta claves sin guion bajo simple)
- [x] 3.8 Bug 3 corregido (`_can_change_qty_on_pos_order` /
      `_can_change_price_on_pos_order`), log de diagnóstico y texto de
      debug retirados, JS/Python confirmados en vivo en el contenedor
- [x] 3.9 Confirmación final del usuario (2026-07-20): Cant. y Precio ya
      quedan clickeables tras storage clear + sesión de PdV nueva
- [ ] 3.10 Pendiente (no bloqueante): confirmar que un usuario SIN esos
      grupos sigue viendo Cant./Precio deshabilitados (no se rompió el
      control de acceso)

## 4. OpenSpec

- [x] 4.1 `openspec validate --changes`
