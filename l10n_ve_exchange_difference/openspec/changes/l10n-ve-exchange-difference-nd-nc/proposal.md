# Feat: Diferencial cambiario de facturas de cliente como Notas de Débito/Crédito

## Why

En Odoo, al conciliar una factura en moneda extranjera contra un pago con una
tasa de cambio distinta, el motor nativo genera un asiento contable genérico e
interno (`exchange_move`) para registrar el diferencial cambiario. Ese asiento:

- No tiene correlativo fiscal real
- No es imprimible de forma directa
- No está vinculado a la factura de origen
- Es transparente para el usuario final

Los clientes venezolanos requieren un documento legal que documente ese
diferencial: una **Nota de Débito** (si hay ganancia cambiaria) o una **Nota de
Crédito** (si hay pérdida) emitida contra la factura original, con secuencial
real y validable en el ATS.

## What Changes

**Interception del motor nativo:**
Sin desactivar el motor de Odoo, se intercepta el hook `_prepare_exchange_difference_move_vals`
en el punto exacto donde Odoo calcula el monto del diferencial, y se redirige
ese monto a una Nota de Débito/Crédito fiscal real en lugar de al asiento genérico.

**Campos nuevos en los modelos:**

| Modelo | Campo | Tipo | Descrip ción |
|--------|-------|------|-----------|
| `res.company` | `l10n_ve_exchange_use_nd_nc` | Boolean | Toggle: usar ND/NC para diferencial |
| `res.company` | `l10n_ve_exchange_note_product_id` | Many2one | Producto para línea de la ND/NC |
| `res.company` | `l10n_ve_exchange_note_pricelist_id` | Many2one | Lista de precios (en moneda de compañía) |
| `account.move` | `l10n_ve_exchange_diff_entry` | Boolean | Marcador de asiento genérico etiquetado |
| `account.move` | `l10n_ve_exchange_original_id` | Many2one | Reversión de ND original (para NC reversa) |
| `account.move` | `l10n_ve_exchange_is_credit_note` | Boolean | Verdadero si NC emitida directamente |
| `account.move` | `l10n_ve_exchange_invoice_id` | Many2one | Factura de origen |
| `account.move` | `l10n_ve_exchange_payment_id` | Many2one | Pago que originó la ND/NC |
| `account.journal` | `l10n_ve_exchange_debit_note_sequence_id` | Many2one | Secuencia propia de ND |

**Métodos sobrescritos:**

| Método | Módulo | Cambio |
|--------|--------|--------|
| `reconcile()` | `account.move.line` | Filtra líneas elegibles, pasa contexto con IDs |
| `_prepare_reconciliation_single_partial()` | `account.move.line` | **[INTERNO]** Stashea pareja real (invoice, payment) |
| `_prepare_exchange_difference_move_vals()` | `account.move.line` | Encola ND/NC en lugar de Odoo generic |
| `_create_exchange_difference_moves()` | `account.move.line` | Crea ND/NC desde cola |
| `_create_exchange_difference_note()` | `account.move.line` | Nueva: construye la ND/NC fiscal |
| `js_remove_outstanding_partial()` | `account.move` | Revierte ND/NC si se rompe conciliación |
| `_reverse_exchange_note()` | `account.move` | Nueva: revierte sin cancelar |
| `_reverse_moves()` | `account.move` | Vincula reversal via `l10n_ve_exchange_original_id` |
| `_compute_name_by_sequence()` | `account.move` | Usa secuencia dedicada de ND |
| `_sequence_matches_date()` | `account.move` | Salta validación de secuencia para ND/NC |

## Qué flujos cambian, y cuáles no

### Incluidos (comportamiento cambia)

**Conciliación de factura de cliente con pago:**
- ✅ `out_invoice` + `out_refund` (incluye ND de cliente nativas)
- ✅ Toggle `l10n_ve_exchange_use_nd_nc` activado en la compañía
- ✅ Moneda distinta entre factura y pago (o diferencia de tasa)
- ✅ Pagos únicos, agrupados, anticipos, pagos parciales (varias cuotas)
- ✅ Compatible con `l10n_ve_igtf` (ambos se aplican independientemente)

### Excluidos (comportamiento NO cambia)

| Caso | Por qué NO | Resultado |
|------|-----------|-----------|
| Factura de proveedor (`in_invoice`) | Guard en `reconcile()` | Comportamiento nativo Odoo |
| Asiento misceláneo | Guard en `reconcile()` | Comportamiento nativo Odoo |
| Toggle desactivado | Guard en `reconcile()` | Comportamiento nativo Odoo |
| Nota reversada ya | Guard en `reconcile()` | Comportamiento nativo Odoo |
| Nota de IGTF del módulo `l10n_ve_igtf` | Guard en `reconcile()` | Comportamiento nativo Odoo |
| Widget Conciliación Bancaria (`account_accountant`) | No pasa por `reconcile()` | Widget maneja diferencial aparte |
| Línea de clase diferente a `asset_receivable` | Guard en `reconcile()` | Comportamiento nativo Odoo |

## Impact

- **Capability**: `exchange-difference-note` (nueva).
- **Módulo**: `l10n_ve_exchange_difference` (NUEVO módulo).
- **Dependencias requeridas**: `account`, `l10n_ve_accountant`, `od_journal_sequence`,
  `l10n_ve_invoice`, `l10n_ve_igtf`, `account_invoice_pricelist`.
- **Cambios necesarios en módulos vecinos**:
  - `l10n_ve_accountant/models/account_move.py`: Remueve `with_context()` por registro
    para evitar RecursionError (reemplaza por delegación directa).
  - `l10n_ve_accountant/models/account_tax.py`: Cambia `active_model ==` a `record._name ==`
    para robustez.
  - `l10n_ve_igtf/models/account_move.py`: Reemplaza Many2many computado por
    One2many directo (evita cascada de recomputes).
- **Tests existentes**: Ninguno en estos módulos se rompe. Los 22 de
  `l10n_ve_accountant/tests/test_real_portion.py` pasan sin cambios.
- **Tests nuevos**: 47 en `l10n_ve_exchange_difference`, cobertura 98%.
- **Riesgo**: Bajo a medio. El riesgo principal es acoplamiento a método
  INTERNO de Odoo (`_prepare_reconciliation_single_partial` verificado en
  19.0-20260710). Incluye guardias de detección en test + runtime.
- **Sin verificar en navegador todavía**: Pendiente UI/workflow testing con
  usuario real en caso de pagos agrupados complejos.

## Datos existentes

El código no toca datos ya publicados. Solo actúa sobre asientos en `draft`.
Las facturas ya conciliadas conservan su asiento genérico de Odoo; los nuevos
solo se crean en reconciliaciones FUTURAS una vez el módulo esté instalado.

Si se desactiva el toggle después de tener ND/NC publicadas, quedan intactas;
la conciliación futura vuelve a usar el asiento genérico nativo.

## Limitaciones conocidas

1. **Acoplamiento a API interna de Odoo:** El método `_prepare_reconciliation_single_partial`
   es INTERNO (línea baja: `_`), no parte de la API pública. Acoplarse a él es
   riesgoso. **Mitigation**: Test de compatibilidad en `test_odoo_core_api_compatibility`,
   runtime guard que detecta cambios de keys en diccionarios. Documentado en
   código con versión exacta verificada.

2. **Solo facturas de cliente:** Las ND/NC solo se emiten para `out_invoice`/`out_refund`.
   Facturas de proveedor siguen el flujo nativo de Odoo sin cambios.

3. **Configuración obligatoria:** Producto, pricelist, diario con secuencia.
   Si faltan, `UserError` en el punto de reconciliación. Validado en tiempo de
   guardado de compañía y de nuevo en runtime (defensa en profundidad).

4. **Secuencia dedicada de ND requerida:** Sin ella, la ND se numeraría con la
   secuencia de FACTURAS del diario de venta (documento fiscal incorrecto).

5. **Reversión no cancela:** Si se rompe la conciliación, la ND se revierte
   (documento nuevo con `reversed_entry_id` apuntando a la original) nunca se
   cancela. Es la política nativa de Odoo para documentos ya posteados.

6. **Pagos agrupados con atribución exacta:** Requiere que Odoo no cambie la
   estructura de `debit_values`/`credit_values` en `_prepare_reconciliation_single_partial`.
   Detectado por test + runtime guard.

7. **Widget de conciliación bancaria:** El widget de Enterprise (`account_accountant`)
   calcula y aplica el diferencial directamente sin pasar por `reconcile()`, así
   que no activa este módulo. Es un flujo legítimo y permitido.

## Hallazgos fuera de alcance

1. **Fixture de composición de tasas en `res.currency.rate`:** Bug del núcleo
   de Odoo donde `_sanitize_vals()` + `_inverse_company_rate()` componen tasas
   incorrectamente si no se pasa `rate` explícito. Corregido en este PR en dos
   archivos de fixture (`test_common_sale_book_igtf_usd_partner_formal.py`,
   `test_common_purchase_book_igtf_usd_provider_formal.py`). Queda como deuda
   técnica en Odoo core.

2. **Perf de Many2many computado:** El cambio a One2many directo en `l10n_ve_igtf`
   es mejora de perf, no bloqueante.

3. **RecursionError en cadenas profundas de super():** Resuelto quitando
   `with_context()` por registro en `l10n_ve_accountant`. No es culpa de este
   módulo, es consecuencia de cadenas de herencia profundas en el proyecto.
