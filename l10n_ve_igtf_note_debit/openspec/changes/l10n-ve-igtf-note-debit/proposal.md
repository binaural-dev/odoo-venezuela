# Feat: Percepción de IGTF como Nota de Débito Fiscal automática

## Why

`l10n_ve_igtf` contabiliza el IGTF (Impuesto a las Grandes Transacciones
Financieras, 3% por defecto) como una línea embebida dentro del mismo
asiento de pago o de cruce de anticipo ("inline"). Ese asiento:

- No es un documento fiscal independiente, no tiene su propio correlativo
- No es imprimible/entregable al cliente como comprobante de la percepción
- No es fácilmente auditable por separado del pago que lo originó

Conforme a las Providencias SENIAT 0071/0102, la percepción de IGTF puede
documentarse como un ajuste por cobrar/pagar independiente. Los clientes que
requieren ese comprobante fiscal real necesitan una **Nota de Débito**
vinculada a la factura de origen, vía `account_debit_note` (Forma Libre, con
su propio número de control), sin perder la compatibilidad de los clientes
que ya operan con el flujo `inline`.

## What Changes

**100% opt-in por compañía** (`igtf_note_debit_mode`): mientras el modo sea
`inline`, ningún método sobrescrito por este módulo cambia el comportamiento
de `l10n_ve_igtf` -- todos delegan en `super()`.

**Campos nuevos:**

| Modelo | Campo | Tipo | Descripción |
|--------|-------|------|-----------|
| `res.company` | `igtf_note_debit_mode` | Selection | `inline` / `debit_note` |
| `res.company` | `igtf_note_debit_product_id` | Many2one | Producto usado como línea única de la ND |
| `res.company` | `igtf_note_debit_include_in_payment_default` | Boolean | Default del checkbox del wizard |
| `res.company` | `igtf_note_debit_vef_journal_id` | Many2one | Diario VEF para el pago aparte del IGTF |
| `res.company` | `igtf_note_debit_valid_journal_ids` / `igtf_note_debit_valid_product_ids` | Json | Computados, para dominios de la vista |
| `account.move` | `origin_payment_to_pay_igtf` | Many2one | Pago de origen que generó la ND |
| `account.move` | `has_pending_igtf_debit_note` | Boolean (compute) | ND de IGTF posteada y sin cobrar |
| `account.move` | `l10n_ve_igtf_note_debit_origin` | Boolean | Marca la ND generada por este flujo |
| `account.payment.register` | `igtf_note_debit_include_in_payment` | Boolean | Checkbox "Incluir IGTF en el pago" |
| `account.payment.register` | `total_amount_with_igtf_note_debit` | Monetary (compute) | Desglose Importe + IGTF = Total |
| `account.payment.register` | `igtf_note_debit_internal_amount_write` | Boolean | Bandera interna, ver "Bugs corregidos" |

**Métodos sobrescritos:**

| Método | Modelo | Cambio |
|--------|--------|--------|
| `compute_bi_igtf` | `account.move` | Base imponible/IGTF reconoce el flujo `debit_note` además del `inline` |
| `remove_igtf_from_account_move` | `account.move` | Dispara reversa por Nota de Crédito en modo `debit_note` |
| `js_assign_outstanding_line` | `account.move` | Separa base/IGTF en conciliación manual (no anticipo) |
| `_create_advance_payment_move` | `account.move` | Cruce de anticipo sin línea embebida, ND aparte |
| `_create_igtf_moves_in_payments` | `account.payment` | No embebe línea de IGTF en modo `debit_note` |
| `_compute_amount` / `_onchange_amount` / `_compute_payment_difference` | `account.payment.register` | Ajustan monto/diferencia cuando el checkbox está desmarcado |
| `_create_payments` | `account.payment.register` | Genera y concilia la ND tras crear el/los pagos |

**Métodos nuevos:**

| Método | Modelo |
|--------|--------|
| `prepare_igtf_payment_debit_note` | `account.move` |
| `settle_igtf_debit_note` / `_settle_igtf_debit_note_with_vef_payment` | `account.move` |
| `create_note_credit_igtf` / `_unreconcile_and_cancel_advance` | `account.move` |
| `_check_igtf_note_debit_group_payment` | `account.payment.register` |

## Historial de implementación: bugs reales corregidos

1. **Conversión de moneda con pago no indexado**: en `_create_payments`, la
   conversión de `payment.igtf_amount` (ya calculado respetando
   `indexed_default`) a moneda de compañía usaba siempre `payment.date`,
   ignorando `indexed_default` -- reintroducía la tasa del pago aunque el
   cálculo base ya usara la tasa de la factura. Corregido: la fecha de
   conversión ahora sigue la misma regla (`payment.date` si es indexado,
   `invoice.invoice_date` si no).

2. **Onchange duplicado** en el wizard: `_onchange_amount` tenía
   `igtf_note_debit_include_in_payment` como trigger además de
   `amount`/`payment_date`, causando que Odoo lo invocara DOS VECES en el
   mismo ciclo de onchange al destildar el checkbox -- la segunda invocación
   caía en `super()` con el flag interno ya reseteado por la primera,
   corrompiendo `custom_user_amount`/`amount_without_difference`. Corregido
   quitando ese trigger redundante.

3. **Code review previo** (5 hallazgos, ya corregidos): el módulo no era
   100% opt-in (duplicaba lógica de `compute_bi_igtf`/
   `remove_igtf_from_account_move` en vez de usar `super()`), la reversa de
   IGTF solo contemplaba ventas, la tolerancia de conciliación tenía lógica
   invertida, y los `@api.depends` del wizard estaban incompletos.

## Impact

- **Capability**: `igtf-note-debit` (nueva).
- **Módulo**: `l10n_ve_igtf_note_debit` (NUEVO módulo).
- **Dependencias requeridas**: `l10n_ve_igtf`, `account_debit_note`.
- **Tests**: 244 tests verdes entre `l10n_ve_igtf`, `l10n_ve_igtf_note_debit`
  y `l10n_ve_exchange_difference`.
- **Riesgo**: Bajo-medio. El acoplamiento principal es a
  `js_assign_outstanding_line`/`_create_advance_payment_move` de
  `l10n_ve_igtf` (no API interna de Odoo), y a la estructura del widget de
  "invoice_outstanding_credits_debits_widget" para leer montos de conversión.

## Limitaciones conocidas

1. Pagos agrupados multi-factura están bloqueados en modo `debit_note` --
   cada factura debe generar su propia ND.
2. Requiere el producto de percepción configurado (validado al guardar la
   compañía) antes de poder activar el modo `debit_note`.
3. El diario VEF para el cobro aparte del IGTF, si no está configurado
   explícitamente, se autodetecta -- puede fallar con `UserError` si no hay
   ningún diario banco/caja VEF disponible sin marcar como IGTF.
