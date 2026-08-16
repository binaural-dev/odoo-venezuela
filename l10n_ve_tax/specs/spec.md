# Spec: l10n_ve_tax - reporte de colision con binaural_tax (invoice_payments_widget)

## Contexto / Bug Report

Al abrir/leer una cotización o pedido de venta (`sale.order`) en instancias con
`odoo-venezuela` (`l10n_ve_tax` + `l10n_ve_igtf`) e `integra-addons` (`binaural_tax`)
instalados, el cómputo de `tax_totals` fallaba con:

```
AttributeError: 'sale.order' object has no attribute 'invoice_payments_widget'
```

### Causa raíz

`account.tax` es extendido tanto por `l10n_ve_tax` como por `binaural_tax`
(integra-addons), y ambos módulos definen un método privado homónimo:
`_get_move_from_base_lines`. Odoo fusiona ambas clases en una sola; cuando dos
módulos aportan un método con el mismo nombre al mismo modelo, solo sobrevive
**una** implementación (la del módulo cargado más tarde en la MRO), y esa es la
que se ejecuta para *cualquier* llamada a `self._get_move_from_base_lines(...)`,
incluidas las hechas desde dentro de `binaural_tax`.

`l10n_ve_tax` se carga después de `binaural_tax`, por lo que su versión de
`_get_move_from_base_lines` (este módulo, `models/account_tax.py:389-402`) es la
que realmente se ejecuta siempre, incluso cuando la invoca
`binaural_tax._prepare_tax_totals`.

El commit `8fd0caa429` (2026-08-09, este módulo) le agregó a
`_get_move_from_base_lines` un fallback que también devuelve el propio
`sale.order` (vía `sale.order.line.order_id`) cuando no hay `account.move`
disponible:

```python
if getattr(r, "_name", None) in ("account.move", "sale.order"):
    return r
...
if "order_id" in getattr(r, "_fields", {}):
    if r.order_id:
        return r.order_id
```

Este comportamiento es correcto y necesario para el uso interno de
`l10n_ve_tax._prepare_tax_totals` (línea 30), que sí valida
`move._name == "account.move"` antes de tratar el resultado como una factura.
El problema apareció porque `binaural_tax._get_total_paid_foreign` consumía el
`move` resultante de esta llamada compartida **sin** esa misma validación,
provocando el `AttributeError` al recibir un `sale.order`.

### Resolución

No se requiere cambio de código en `l10n_ve_tax`: su implementación de
`_get_move_from_base_lines` y de `_prepare_tax_totals` ya es correcta y
defensiva. El fix se aplicó del lado de `binaural_tax`
(`integra-addons`, PR https://github.com/binaural-dev/integra-addons/pull/2561),
agregando el mismo guard `move._name == "account.move"` antes de acceder a
`invoice_payments_widget`.

Este documento se agrega en `l10n_ve_tax/specs/` únicamente como registro/reporte
del origen del bug (el commit disparador vive en este módulo), para trazabilidad
cruzada entre ambos repos.

### Riesgo remanente (fuera de alcance de este fix)

Ambos módulos siguen definiendo un método homónimo `_get_move_from_base_lines`
sobre `account.tax`. Cualquier cambio futuro a la implementación de
`l10n_ve_tax` (la que efectivamente se ejecuta) puede volver a afectar
silenciosamente el comportamiento asumido por `binaural_tax`, ya que no hay
override explícito ni namespacing entre ambos. Se recomienda evaluar en una
iteración futura renombrar uno de los dos helpers (o unificarlos) para eliminar
la colisión de raíz.
