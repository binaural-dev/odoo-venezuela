## 1. l10n_ve_rate — `use_last_rate` en `compute_rate`

- [x] 1.1 `compute_rate(..., use_last_rate=False)`: con `True` y sin tasa exacta busca el mayor `name <= rate_date` por compañía (activa y luego raíz); por defecto se mantiene la fecha exacta
- [x] 1.2 Sin ninguna tasa anterior se conserva el `UserError` (o `{}` con `raise_if_not_found=False`); la moneda de la compañía sigue resolviendo `1.0/1.0`
- [x] 1.3 Bump `l10n_ve_rate` 19.0.1.3.0 -> 19.0.1.4.0
- [x] 1.4 Tests en `l10n_ve_rate/tests/test_res_currency_rate.py` (`TestComputeRateUseLastRate`)

## 2. l10n_ve_accountant — tasa exacta al publicar los asientos manuales

- [x] 2.1 Hook `_is_rate_deferrable()` y `_is_exchange_journal_entry()`: solo el asiento manual es diferible; pagos, extractos, inventario, PdV, reversos y diferencia cambiaria exigen la tasa al crear
- [x] 2.2 `_compute_rate_for_documents`: asiento diferible en borrador sin tasa queda con tasa 0; el reverso de un asiento hereda la tasa del original
- [x] 2.3 `create()`: la consulta de tasa de referencia no lanza para asientos diferibles y el reverso hereda la tasa; el resto de documentos sigue lanzando
- [x] 2.4 `_post`: recalcula la tasa exacta de `date` (con `with_company`) y fuerza el recálculo de `foreign_debit`/`foreign_credit` antes del `super`; no recalcula tasa manual con valor, `posted_before` con tasa ni asientos futuros con `soft=True`; `UserError` si no existe la tasa
- [x] 2.5 Red de seguridad tras `_post`: `entry` publicado con moneda alterna y sin tasa lanza `UserError` (excluye diferencia cambiaria)
- [x] 2.6 `@api.onchange("date")` `_onchange_date_rate_warning`: aviso no bloqueante
- [x] 2.7 Bump `l10n_ve_accountant` 19.0.1.0.44 -> 19.0.1.0.46 y traducciones en `i18n/es_VE.po`
- [x] 2.8 Tests en `l10n_ve_accountant/tests/test_entry_deferred_rate.py` (creación en borrador sin tasa, publicar sin tasa lanza, publicar con tasa en cabecera y líneas, tasa manual no se recalcula, manual con tasa 0 sí, facturas/notas/recibos exactos, factura con tasa manual sin tasa lanza, pago, extracto, inventario, valores del hook, publicación `soft` de un asiento futuro, fecha de bloqueo, cron, reverso, compañía sin moneda alterna, aviso del onchange) y ajuste de `test_entry_rate_date.py`; se elimina `test_entry_last_rate.py`

## 3. Verificación

- [ ] 3.1 Correr `l10n_ve_rate` y `l10n_ve_accountant` completos tras el upgrade (`-u l10n_ve_rate,l10n_ve_accountant`)
- [ ] 3.2 Navegador: asiento manual en sábado se guarda en borrador con aviso, no se publica sin tasa y al cargar la tasa del sábado se publica con ella
- [ ] 3.3 Navegador: factura en sábado sin tasa (con y sin tasa manual) bloquea con «There is no rate assigned»; pago en sábado también
- [ ] 3.4 Flujo de inventario/valoración y de sesión de PdV en día sin tasa, y extracto bancario (no probados de punta a punta)
- [ ] 3.5 Cierre de ejercicio y apertura del 1 de enero: el error de falta de tasa aparece al publicar
- [ ] 3.6 Push de la rama y revisión del PR
- [ ] 3.7 Archivar el cambio (`openspec archive`) al cerrar el ticket (lo hace el líder)
