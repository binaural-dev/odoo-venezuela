# Spec delta: invoice-accounting-date-timezone

## ADDED Requirements

### Requirement: Los defaults de fecha de factura usan la zona horaria del usuario

El sistema SHALL usar `fields.Date.context_today` como `default` de todo
campo de fecha de `account.move` que alimente la fecha contable (`date`), y
SHALL NOT usar `fields.Date.today`. Esto aplica a `invoice_date_display`
(`l10n_ve_accountant`) e `invoice_date` (`l10n_ve_invoice`).

Motivo: `fields.Date.today()` devuelve `date.today()` — la fecha local del
proceso Odoo, que en despliegue containerizado es UTC — mientras que el
resto del framework contable decide sobre fechas con
`fields.Date.context_today()`, que respeta `context['tz']` / `user.tz`.
Mezclar ambos relojes produce un desfase de un día en cualquier zona con
offset negativo durante las últimas horas del día local.

#### Scenario: Factura creada por RPC en la franja horaria de desfase

- **GIVEN** un servidor Odoo con reloj en UTC y un usuario con tz
  `America/Caracas` (UTC-4)
- **AND** la hora actual es `2026-07-28 01:22 UTC` (`2026-07-27 21:22` en
  Caracas)
- **WHEN** se crea una `account.move` de venta sin pasar
  `invoice_date_display` explícitamente
- **THEN** `invoice_date_display` es `2026-07-27` (fecha en Caracas), no
  `2026-07-28`

#### Scenario: Servidor y usuario en la misma zona horaria

- **GIVEN** un servidor y un usuario en la misma zona horaria
- **WHEN** se crea una factura sin fecha explícita
- **THEN** el comportamiento es idéntico al anterior al fix

### Requirement: Las facturas del PdV se publican y no se tratan como futuras

El sistema SHALL garantizar que la fecha contable (`date`) de una factura
generada desde el Punto de Venta nunca sea posterior a
`fields.Date.context_today()` evaluado en el mismo contexto de usuario, para
que `_post(soft=True)` de core no la clasifique como movimiento futuro.

Una factura clasificada como futura recibe `auto_post='at_date'` y queda en
borrador; el `_generate_and_send()` posterior del flujo del PdV
(`pos_order.py:1157`) la rechaza con el `UserError` de core
`"You can't generate invoices that are not posted."`, y el `UserError`
propaga por `sync_from_ui` haciendo rollback de toda la orden.

#### Scenario: Validar una orden del PdV a las 21:00 hora Venezuela

- **GIVEN** un servidor en UTC, un cajero con tz `America/Caracas` y la hora
  local entre las 20:00 y las 23:59
- **WHEN** el cajero valida una orden con factura desde el PdV
- **THEN** la factura queda en estado `posted`
- **AND** la orden del PdV se sincroniza sin error
- **AND** `invoice_date`, `invoice_date_display` y `date` coinciden con la
  fecha local en Venezuela

#### Scenario: Validar una orden del PdV fuera de la franja

- **GIVEN** las mismas condiciones pero con hora local entre las 00:00 y las
  19:59
- **WHEN** el cajero valida una orden con factura
- **THEN** la factura queda en estado `posted` (comportamiento sin cambios)

### Requirement: La sincronización entre `invoice_date` e `invoice_date_display` no depende solo de onchange

El sistema SHALL NOT depender de los `@api.onchange` que sincronizan
`invoice_date` con `invoice_date_display`: solo se ejecutan en el
formulario web. En creación programática o por RPC (PdV, `sale.order`,
facturación en lote, API externa) cada campo cae en su propio `default`, por
lo que ambos defaults SHALL ser coherentes entre sí y con la zona horaria
del usuario.

#### Scenario: Creación programática sin pasar por el formulario

- **GIVEN** el flujo del PdV, que pasa `invoice_date` en `_prepare_invoice_vals`
  pero no `invoice_date_display`
- **WHEN** se crea la factura
- **THEN** `invoice_date_display` toma su `default` tz-aware y la fecha
  contable resultante corresponde al día local del usuario
