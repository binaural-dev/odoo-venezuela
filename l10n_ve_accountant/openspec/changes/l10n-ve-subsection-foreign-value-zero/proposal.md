# Fix: una subsección puede recibir importe en moneda alterna y descuadrar el asiento

## Why

Detectado auditando el mismo defecto que dejaba infacturable la cotización
S11508 de CDD Las Mercedes (tarea 82254): `line_subsection`, el
`display_type` que **Odoo 19 agregó a la familia de líneas de maquetado**
(`line_section`, `line_note`), quedó fuera de las tuplas que este repo tenía
hardcodeadas.

En `_get_foreign_value()` la rama 2 devuelve `0.0` para sección y nota,
justamente porque una línea de maquetado no es contable y no puede llevar
importe. Con `line_subsection` ausente de esa tupla, una subsección **cae por
las ramas siguientes** y puede terminar con un `foreign_balance` distinto de
cero: descuadra el asiento en la columna de moneda alterna.

Este es el más silencioso de los dos bugs de la familia. El de
`l10n_ve_invoice` es ruidoso y sin salida —lanza `ValidationError` y no
podés facturar—, así que se ve al instante. Este no lanza nada: el asiento se
postea y queda descuadrado en la moneda alterna, donde nadie mira hasta que
un reporte no cierra.

Es el mismo error de familia que ya se corrigió en
`l10n-ve-real-portion-excludes-line-section`, en otro método
(`_distribute_invoice_real_portion`), y por la misma causa: una tupla de
`display_type` incompleta.

## What Changes

Se agrega `"line_subsection"` a la tupla de la rama 2 de
`_get_foreign_value()`, con el comentario que explica de dónde viene el
`display_type` y qué pasaba sin él.

## Capabilities

### New Capabilities
- `foreign-value-layout-lines`: el cálculo del importe en moneda alterna de
  un apunte (`_get_foreign_value`) debe devolver cero para toda la familia de
  líneas de maquetado (`line_section`, `line_subsection`, `line_note`), antes
  de evaluar cualquier otra rama, de modo que una línea no contable nunca
  aporte al cuadre de la columna alterna.

## Impact

- Archivo: `l10n_ve_accountant/models/account_move_line.py`
  (`_get_foreign_value`, rama 2).
- Módulos afectados: cualquier cliente con `l10n_ve_accountant` en Odoo 19
  que use subsecciones en documentos con moneda alterna configurada.
- Ver también el cambio hermano en `l10n_ve_invoice`
  (`l10n-ve-invoice-subsection-blocks-invoicing`), que corrige la misma
  omisión en los tres guards de línea de producto. Los dos son la misma
  causa raíz y van juntos.
- **Posible corrección de datos.** A diferencia del cambio hermano, acá no
  había guard que impidiera persistir: un asiento posteado con una subsección
  puede tener hoy la columna alterna descuadrada. Este fix corrige el cálculo
  de ahora en adelante; los asientos ya posteados hay que revisarlos a mano.
  Consulta para detectarlos en la sección de tasks.
- Bump de manifest `19.0.1.0.15` → `19.0.1.0.16`.
