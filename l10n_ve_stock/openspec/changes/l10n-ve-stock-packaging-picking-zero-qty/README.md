# l10n-ve-stock-packaging-picking-zero-qty

Corrige que un picking con package_qty=0 no imprima ninguna etiqueta de embalaje.

Además, restringe el nombre del destinatario en la etiqueta a pickings de salida
con `partner_id` seteado, y cambia a `partner_id.display_name` (evita un
`TypeError` real visto en staging cuando `partner_id` está vacío).
