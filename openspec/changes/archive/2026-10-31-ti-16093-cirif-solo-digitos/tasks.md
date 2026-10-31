## 0. Decisiones

- [x] 0.1 2026-10-31: solo dígitos con todos los prefijos, P y C incluidos ("deja los prefijos, pero donde se teclea
      los dígitos, es mejor no dejar que ni siquiera pongan"). El Kiosko deja libres P y C; el formulario de
      contacto no
- [x] 0.2 2026-10-31: se filtra en el navegador al escribir; no se agrega validación nueva en el servidor (el ticket
      pide no tener que borrar lo escrito)
- [x] 0.3 2026-10-31: el `vat` deja de usar el widget de `partner_autocomplete` (búsqueda IAP por número fiscal, sin
      resultados con el número sin prefijo); el `name` lo conserva

## 1. Implementación

- [x] 1.1 Widget `l10n_ve_vat` (`static/src/fields/vat_field/vat_field.{js,xml}`): `CharField` que deja solo los
      dígitos en cada `input`, mantiene el cursor y pide `inputmode="numeric"`
- [x] 1.2 `views/res_partner.xml`: `widget="l10n_ve_vat"` en el `vat` junto a `prefix_vat`
- [x] 1.3 `res.partner._get_view`: el `vat` con `field_partner_autocomplete` vuelve a `l10n_ve_vat`
- [x] 1.4 Assets en `web.assets_backend`, `point_of_sale._assets_pos` (el PdV pinta este formulario) y
      `web.assets_unit_tests`
- [x] 1.5 Traducción es_VE del nombre del widget; versión del manifest 19.0.1.8.2
- [x] 1.6 Archivar el change y volcarlo en `openspec/specs/l10n_ve_contact/spec.md`

## 2. Tests

- [x] 2.1 `tests/test_vat_field_widget.py`: el `vat` del formulario de contacto y de las vistas primarias construidas
      sobre él (la del PdV) usa `l10n_ve_vat`; con un arch como el de `partner_autocomplete`, `_get_view` devuelve
      `l10n_ve_vat`; el widget está en los bundles del backend y del PdV
      (`odoo -c /home/odoo/.config/odoo.conf -d posconsultoria_85594 --test-tags /l10n_ve_contact:TestVatFieldWidget
      --stop-after-init --http-port 9998 --workers=0`, tras `-u l10n_ve_contact`: 5 en verde; la prueba de las vistas
      primarias se salta si no hay ninguna con `vat`, como en una base sin `l10n_ve_pos`. La suite del módulo da 3
      errores previos en `test_name_change_*`, por la tasa USD del día que falta en esa copia)
- [x] 2.2 `static/tests/unit/vat_field.test.js`: letras tecleadas, CI/RIF pegado, prefijo P, letra sola sin dejar
      cambios pendientes, `inputmode`, cursor y `keepVatDigits`
      (`/web/tests?filter=@l10n_ve_contact/unit` en `posconsultoria_85594`: 8/8 en verde; el CI no corre Hoot)
- [x] 2.3 Navegador en `posconsultoria_85594` (con `partner_autocomplete` instalado), con teclas reales por CDP:
      contacto nuevo del backend, "12a3B4ñ-." → "1234" y "V-27.436.42x" pegado → "2743642"; "Caja 1" del PdV,
      "Editar contacto": "30a40B50ñ.-" → "304050" y "J-40.123.456-7" pegado → "401234567"; en los dos el campo
      es `o_field_l10n_ve_vat` con `inputmode="numeric"`
