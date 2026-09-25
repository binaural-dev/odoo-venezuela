# Tasks

## 1. Backend

- [x] 1.1 `controllers/orders.py`: `identify` e `identify/create` añaden
      `vat`/`prefix_vat` al `read(...)` del partner devuelto
- [x] 1.2 `models/res_partner.py` (nuevo): `_load_pos_self_data_read` inyecta
      `vat`/`prefix_vat` sobre el read del core (sobreviven a re-sync)
- [x] 1.3 Registrar `res_partner` en `models/__init__.py`

## 2. Verificación

- [x] 2.1 Confirmar que `vat`/`phone`/`prefix_vat` están en el esquema de
      campos del cliente (`res.partner._load_pos_data_fields`: core trae
      `vat`/`phone`, `l10n_ve_pos` añade `prefix_vat`), para que
      `connectNewData` no rechace los campos
- [ ] 2.2 Navegador: identificarse en el kiosko y confirmar que
      `order.partner_id.vat` llega poblado al llegar a la pantalla de pago
      (validable desde `binaural_megasoft_self_order`)

## 3. OpenSpec

- [x] 3.1 `openspec change validate l10n-ve-pos-self-order-expose-identified-vat` → válido
