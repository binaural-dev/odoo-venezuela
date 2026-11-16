## Why

Ticket https://www.binauraldev.com/odoo/helpdesk/58/tickets/16093 (referencia #16131): el campo
CI/RIF del contacto deja escribir letras y el error llega después ("The vat field only accepts
numbers", en el onchange de `vat`/`prefix_vat`), así que hay que borrar a mano lo escrito por
error. Se pide que el campo no deje escribir letras.

Desde O19 el PdV no tiene un formulario propio de contacto: abre en un diálogo
`point_of_sale.res_partner_action_edit_pos`, que `l10n_ve_pos` apunta a
`view_partner_form_pos`, una vista primaria construida sobre `base.view_partner_form` ya
combinado con `l10n_ve_contact`. Lo que se haga en el formulario del backend llega también al PdV.

Al probarlo en `posconsultoria_85594` apareció un segundo problema: `partner_autocomplete`
(auto_install) sobrescribe en `res.partner._get_view` el widget de `name`, `vat` y `duns` de
todo formulario de contacto con `field_partner_autocomplete`. Un widget puesto solo en el XML se
pierde.

## What Changes

- Nuevo widget `l10n_ve_vat` (`static/src/fields/vat_field/`): un `CharField` que, en cada
  evento `input`, deja solo los dígitos ASCII y mantiene el cursor donde se escribía. Cubre lo
  tecleado, lo pegado ("V-12.345.678" → "12345678") y lo dictado. Pide el teclado numérico
  (`inputmode="numeric"`) en tabletas y teléfonos.
- Aplica con cualquier prefijo, P (pasaporte) y C incluidos: la letra va en `prefix_vat` y el
  número solo lleva dígitos, la misma regla de `_check_vat` (`^[0-9]*$`).
- `views/res_partner.xml`: el `vat` junto a `prefix_vat` usa `widget="l10n_ve_vat"`.
- `res.partner._get_view`: en los formularios, el `vat` al que `partner_autocomplete` le puso
  `field_partner_autocomplete` vuelve a `l10n_ve_vat`. Gana porque `l10n_ve_contact` carga
  después de `partner_autocomplete` (profundidad 9 contra 6 en el grafo de dependencias). La
  búsqueda IAP por número fiscal no encuentra nada con el número sin prefijo, así que no se
  pierde nada útil; el autocompletado del nombre sigue igual.
- Assets: el widget va en `web.assets_backend` y en `point_of_sale._assets_pos`. Sin él en el
  bundle del PdV, el campo caería al char normal (con un aviso en consola) y dejaría escribir
  letras. Declararlo no hace nada si `point_of_sale` no está instalado.
- Traducción es_VE del nombre del widget ("CI/RIF (solo dígitos)").

## Non-goals

- No se agrega una validación nueva en el servidor: importaciones, API y el onchange actual
  quedan como están. El onchange sigue validando con `_check_vat` cuando el prefijo es V/E y no hay
  nombre.
- No se toca el Kiosko (`l10n_ve_pos_self_order`): tiene su propia pantalla de identificación,
  con teclado numérico, y deja libres P y C.
- No se migran los `vat` ya guardados con letras o separadores (por ejemplo un pasaporte "AB123456"):
  se quedan así mientras nadie escriba en el campo. El onchange tampoco los detecta, porque solo
  valida cuando el contacto no tiene nombre.

## Capabilities

- `l10n_ve_contact`: ADDED "CI/RIF solo con dígitos al escribir".

## Impact

- **Módulo tocado:** `l10n_ve_contact` (19.0.1.8.1 → 19.0.1.8.2).
- **Despliegue:** `-u l10n_ve_contact` (vista, assets y traducción). Sin cambio de esquema. Un PdV
  abierto en el navegador toma el bundle nuevo al recargar la página.
- **`vat` ya guardados con letras o separadores:** al escribir cualquier cosa en el campo, el
  widget filtra el valor completo y pierden todo lo que no sea dígito (un pasaporte `P` "AB123456"
  al que se le agrega un "7" queda en "1234567"). Antes de desplegar conviene medirlos en la base
  del cliente:
  `SELECT prefix_vat, count(*) FILTER (WHERE vat ~ '[^0-9]') FROM res_partner WHERE vat <> '' GROUP BY 1;`
  (en `posconsultoria_85594`: ninguno).
- **Efecto en otros módulos:** cualquier formulario de `res.partner` donde `partner_autocomplete`
  ponga su widget en `vat` pasa a `l10n_ve_vat`, también fuera del formulario principal. El campo
  `name` conserva el autocompletado de `partner_autocomplete`.
