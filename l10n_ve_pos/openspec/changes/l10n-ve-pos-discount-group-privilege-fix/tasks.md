# Tasks

## 1. Fix (`privilege_id` compartido con el acceso base al PdV)

- [x] 1.1 `data/res_group.xml`: `privilege_id` de
      `group_authorized_discount_pos` → `eval="False"`, mismo patrón que
      `security/res_group.xml` para `group_change_qty_on_pos_order` /
      `group_change_price_on_pos_order`

## 2. Verificación

- [ ] 2.1 `-u l10n_ve_pos` en el contenedor `proj` (BD `pos`)
- [ ] 2.2 Confirmar en `res_groups` que `privilege_id` de
      `group_authorized_discount_pos` quedó en `NULL`
- [ ] 2.3 Confirmar en Ajustes → Usuarios que "Authorized discount pos"
      aparece como checkbox independiente en "Extra Rights", combinable
      con Usuario/Administrador de Point of Sale
- [ ] 2.4 Confirmación del usuario en navegador (no se verifica en esta
      sesión — ver `[[feedback-no-comandos-pesados-sin-permiso]]`)

## 3. OpenSpec

- [x] 3.1 `openspec validate --changes`
