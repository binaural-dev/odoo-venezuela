# Feat: Descuento global en pedidos de venta y facturas, con límites y aprobación

## Why

Odoo implementa el descuento global del pedido de venta con una línea de
producto de precio negativo (producto de descuento). La localización venezolana
prohíbe productos negativos (`_check_price_in_zero`, libros fiscales, notas de
crédito), por lo que hacía falta un descuento global que se comporte como el
nativo pero sin línea negativa, generando el apunte contable en una cuenta
configurada y manteniendo el IVA y los libros exactos.

Además `discount_fixed` (descuento por línea en importe) solo existía en
facturas: un pedido con importe fijo no podía viajar a la factura.

## What Changes

- **Esquema por documento** (`discount_mode`) en `sale.order` y en facturas de
  cliente: porcentaje en líneas, importe en líneas, global sobre Subtotal o
  global sobre Total. Son excluyentes entre sí y se heredan del pedido a la
  factura y a su nota de crédito.
- **Asistente "Descuento"** (`l10n_ve.discount.wizard`) en pedido y factura.
  El botón solo se muestra con el ajuste nativo de Ventas "Descuentos" y se oculta si la compañía
  limita el método y no deja ninguno marcado.
- **Cuenta del descuento global** obligatoria por compañía
  (`global_discount_account_id`), distinta de la del descuento por línea.
  - Global sobre Subtotal: escribe `discount` o `discount_fixed` en las líneas
    y el apunte usa la cuenta global.
  - Global sobre Total: no toca líneas ni IVA; un apunte de débito en la cuenta
    global baja la cuenta por cobrar y `tax_totals` muestra el descuento.
- **`discount_fixed` en `sale.order.line`**, compartido con la línea de factura
  mediante el mixin `l10n_ve.discount.line.mixin` (`l10n_ve_invoice`).
- **Límites opcionales e independientes**, visibles solo con el ajuste de Ventas
  "Descuentos" activo:
  - *Limitar método de descuento*: solo los métodos marcados (líneas %, líneas importe,
    global sobre subtotal, global sobre total) se pueden aplicar, **por cualquier usuario**
    (también al escribir un descuento a mano en una línea).
  - *Limitar el descuento máximo* (por esquema, en %): se aplica por sí solo, con o sin
    límite de método. Quien lo excede y no es aprobador queda en
    `discount_approval_state = exceeds` al aplicarlo (aviso en el documento). Al confirmar el
    pedido, o publicar la factura, pasa a `to_approve` (etapa "Descuento por aprobar" del pedido)
    y un aprobador lo aprueba (continúa el flujo natural) o lo rechaza. Los aprobadores nunca entran.
  - En la etapa, el pedido queda bloqueado (campos, líneas y botón Descuento). Sin aprobadores
    asignados no se entra en la etapa (error). Se notifica a los aprobadores al entrar (mensaje,
    actividad y aviso) y al dueño del documento al aprobar o rechazar. Volver a cotización
    reinicia la aprobación.
  - *Aprobar descuentos excedentes*: solo existe con el máximo activo. Sin él, exceder el
    máximo es un error y el descuento no se aplica.
  - Un único permiso nuevo, `Aprobar descuentos excedentes`, en su propia sección
    ("Control de descuentos"), fuera del selector de Ventas.
- **Bloqueo mutuo con el deducible** (`l10n_ve_deductible`): un documento
  deducible no admite ningún descuento y un documento con descuento no puede
  pasar a deducible.
- **Los campos del esquema y la aprobación no se escriben directamente**:
  solo cambian con el botón Descuento y las acciones aprobar/rechazar. La marca
  interna que salta las validaciones vive en el cursor del servidor, no en el
  contexto (un cliente RPC puede enviar cualquier clave de contexto).
- **Alternos de los apuntes de descuento** (`display_type='discount'`): débito y crédito en moneda
  alterna calculados como `l10n_ve_accountant` calcula los de las líneas (precio alterno bruto menos
  subtotal alterno; sobre el total, proporción del total alterno).
- **Totales**: el widget y el PDF muestran siempre "Subtotal"; el descuento sale en positivo, antes
  del subtotal (global sobre subtotal) o después de impuestos (global sobre total), también en los
  bloques de moneda alterna y bolívares.
- Utilidad común de reparto `l10n_ve_invoice/tools/discount.py` (`spread_amount`)
  usada por el descuento global y por el deducible.

## Impact

- Módulos: `l10n_ve_sale`, `l10n_ve_invoice` (mixin de línea, utilidad de
  reparto, gancho `_get_line_discount_type`), `l10n_ve_deductible` (motivo de
  rechazo y reparto compartido).
- `l10n_ve_invoice_digital`: TFHKA rechaza el descuento global sobre el Total (la imprenta no lo
  admite); los demás esquemas se envían por línea.
- `l10n_ve_invoice/tests/common.py` y las pruebas de `l10n_ve_invoice` que lo usan NO son del
  descuento: corrigen 60 errores por falta de tasa del día que ya existían en la rama vertical y se
  mantienen en este PR para que sus pruebas pasen y el PR pueda aprobarse.
- Sin migración: los campos nuevos nacen vacíos y los existentes no cambian.
