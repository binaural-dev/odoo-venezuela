# Fix: `is_isrl_retention_available` no se recalcula al configurar el concepto de pago del producto

## Why

Al crear una factura de proveedor con una línea de producto tipo
"Servicio" que todavía no tiene "Concepto de pago" (ISLR) configurado, el
campo calculado y almacenado `is_isrl_retention_available` (en
`account.move`) queda en `False`. Si luego se le asigna el concepto de
pago al producto (sin tocar la línea de la factura), la factura sigue sin
aparecer como disponible en el selector "Retención de" del wizard de
Retención de ISLR (`account.retention`, dominio `allowed_lines_move_ids`
en `odoo-venezuela/l10n_ve_payment_extension/models/account_retention.py`),
aunque la condición de negocio ya se cumple.

Causa raíz en `models/account_move.py`:

```python
@api.depends(
    "invoice_line_ids",
    "invoice_line_ids.product_id",
)
def _compute_retention_islr_avalability(self):
    for record in self:
        record.is_isrl_retention_available = any(
            line.product_id.product_tmpl_id.type == 'service' and
            line.product_id.product_tmpl_id.payment_concept
            for line in record.invoice_line_ids
        )
```

El `@api.depends` solo escucha cambios en `invoice_line_ids` y en
`invoice_line_ids.product_id` (es decir, qué producto está en la línea).
No incluye `invoice_line_ids.product_id.product_tmpl_id.payment_concept`,
que es el campo que realmente determina el resultado del cómputo. Al
editar `payment_concept` directamente en el producto (sin cambiar de
producto en ninguna línea), Odoo no tiene registrado ese trigger de
recompute y el campo `store=True` se queda con el valor calculado en el
momento de creación de la factura.

## What Changes

- `models/account_move.py`: se agrega
  `"invoice_line_ids.product_id.product_tmpl_id.payment_concept"` al
  `@api.depends` de `_compute_retention_islr_avalability`.
- Bump de manifest: `19.0.2.0.29` -> `19.0.2.0.30`.

## Non-goals

- No se cambia la condición de negocio en sí (producto tipo servicio +
  `payment_concept` configurado) — solo se corrige cuándo se recalcula.
- No se agrega ningún mecanismo retroactivo para facturas ya existentes
  que quedaron con el valor stale; para esas, el workaround inmediato es
  quitar y volver a agregar la línea del producto (o correr una acción de
  servidor que llame `_compute_retention_islr_avalability()` sobre ellas).
