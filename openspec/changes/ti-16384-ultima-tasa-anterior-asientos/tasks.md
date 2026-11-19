## 1. l10n_ve_rate — última tasa anterior en `compute_rate`

- [x] 1.1 `compute_rate(..., use_last_rate=False)`: con `True` y sin tasa exacta busca el mayor `name <= rate_date` por compañía (activa y luego raíz); por defecto se mantiene la fecha exacta
- [x] 1.2 Sin ninguna tasa anterior se conserva el `UserError` (o `{}` con `raise_if_not_found=False`); la moneda de la compañía sigue resolviendo `1.0/1.0`
- [x] 1.3 Bump `l10n_ve_rate` 19.0.1.3.0 -> 19.0.1.4.0
- [x] 1.4 Tests en `l10n_ve_rate/tests/test_res_currency_rate.py` (`TestComputeRateUseLastRate`): fecha exacta gana, fin de semana, entre dos tasas, fecha futura, nunca usa tasa posterior, sin tasa previa lanza o devuelve `{}`, moneda de la compañía, `Datetime`, default exacto

## 2. l10n_ve_accountant — qué documentos exigen tasa exacta

- [x] 2.1 Hook `_is_exact_rate_required()`: `True` para facturas/notas/recibos y asientos con `origin_payment_id`; `False` para el resto de `entry`, incluida la diferencia cambiaria
- [x] 2.2 `_compute_rate_for_documents` usa `with_company(move.company_id)` y `use_last_rate=not required`
- [x] 2.3 `create()` solo consulta la tasa del día si hay tasa manual y sin lanzar (`raise_if_not_found=False`); sin tasa de referencia no publica el mensaje de chatter
- [x] 2.4 Bump `l10n_ve_accountant` 19.0.1.0.44 -> 19.0.1.0.45
- [x] 2.5 Tests en `l10n_ve_accountant/tests/test_entry_last_rate.py` (fin de semana, fecha futura, feriado entre tasas, tasa fija al cargar una tasa después, sin tasa previa lanza, diferencia cambiaria, reverso de asiento de fin de semana, facturas/notas/recibos exactos, asiento de pago exacto, valores del hook, multicompañía, tasa manual sin tasa del día, asiento virtual) y ajuste de `test_entry_rate_date.py`

## 3. Verificación

- [ ] 3.1 Correr `l10n_ve_rate` y `l10n_ve_accountant` completos tras el upgrade (`-u l10n_ve_rate,l10n_ve_accountant`)
- [ ] 3.2 Navegador: asiento manual en sábado usa la tasa del viernes y no cambia al cargar la tasa del sábado
- [ ] 3.3 Navegador: factura en sábado sin tasa sigue bloqueando con «There is no rate assigned»; pago en sábado también
- [ ] 3.4 Flujo de stock/valoración y extracto bancario en día sin tasa (no se probó de punta a punta)
- [ ] 3.5 Factura/asiento con tasa manual en fecha sin tasa: ya no falla al crearse (revisar cierre de ejercicio y PdV)
- [ ] 3.6 Archivar el cambio (`openspec archive`) al cerrar el ticket (lo hace el líder)
