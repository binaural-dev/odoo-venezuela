# Proposal: `l10n_ve_donation` 19 con la lógica de odoo-venezuela#1440

## Metadata

| Campo | Valor |
|---|---|
| Change ID | `ta-86967-donation-module-1440-port` |
| Tarea | [Tarea 86967](https://binaural.odoo.com/odoo/project.task/86967) |
| Tipo | MIG / FEAT |
| Estado | Implementado |
| Módulo destino | `l10n_ve_donation` |
| Origen | Lógica de donaciones de odoo-venezuela#1440 (versión 17, usada por clientes) |

## Contexto

Un cliente que usa esa lógica en Odoo 17 (en producción desde el 1-3 ago 2026)
migra a Odoo 19 con saldos iniciales. Sus cambios de donaciones (tickets 15394, 15445, 15672)
viven solo en #1440 y no existen en `17.0`, `maintenance-17.0`, `19.0` ni
`maintenance-19.0`. El módulo V19 (`19.0.2.0.6`) nació antes que el backport
de 17 y divergió: los dos modelan la donación de forma distinta (contacto
forzado a la compañía, almacén global, motivo 'Autoconsumo' forzado,
donación por scrap).

Decisión: la lógica de #1440 **sustituye por completo** al módulo
de V19 (no es una extensión ni un parche encima). El scrap sale del alcance.

## Situación actual → esperada

| Tema | V19 (`19.0.2.0.6`) | Esperado (`19.0.3.0.0`) |
|---|---|---|
| Contacto de cabecera en pedido, picking y asiento | forzado al partner de la compañía (error si se cambia) | el contacto real (donante/beneficiario); solo las líneas de los asientos `entry` llevan el partner de la compañía |
| Almacén de donación | uno global | uno por compañía/sucursal |
| Donación de mercancía | `stock.scrap` con `is_donation` | picking del menú Inventario > Operaciones > Transferencias > Donaciones, o picking de un pedido de donación |
| Motivo de traslado | 'Autoconsumo' forzado | 'Donación' por defecto, solo lectura en la vista, **agregado** a los permitidos |
| Asiento de valoración | hook sobre el scrap | hook sobre el picking de salida sin pedido (API de stock de 19) |
| Documento de la entrega | certificado solo de asiento manual | documento de la entrega de mercancía con el costo de `stock.move.value` (hoy el Recibo de donación, ver `ta-86967-donation-received-documents`) |
| Validación de configuración y devoluciones | no existen | se valida destino y cuenta de valoración; la devolución de una donación sin pedido está bloqueada |
| `action_post` de donación | `_post(soft=True)` salta el wizard de alerta y deja la NC en borrador | respeta el wizard: una confirmación publica la factura y su NC, y procesa todas las facturas del lote |
| Nota de crédito automática | creada con `skip_invoice_sync` (queda en 0,00, sin impuesto ni línea por cobrar) | sin esa llave: copia base, impuesto y total de la factura |
| Asiento manual de donación | `is_donation` oculto en asientos nuevos; partner y sufijo `- <ref>` escritos al publicar | `is_donation` editable en borrador; partner de la compañía asignado en borrador; publicar no escribe nada (diarios con hash) |
| Botón "Crear factura" | visible en una donación sin pedido ya validada | oculto |

## Por qué no se parchea V19 "ahí mismo"

Los dos módulos dependen de comportamientos incompatibles (contacto
forzado vs libre, scrap vs picking). Mezclarlos dejaría dos caminos para la
misma donación. Por eso se sustituye.

## Alcance

**Dentro**
- Lo de #1440 que no es del scrap, portado a la API de 19: beneficiario real en la
  cabecera, certificado de entrega, hook contable del asiento de valoración, `is_donation`
  unificado en el picking, validación de la configuración y bloqueo de devoluciones.
- Lo exclusivo de V19 que se conserva: hook `_l10n_ve_skip_refund_origin_validation`,
  `_reverse_moves` con API 19 (sin `skip_invoice_sync`), baja de activos
  (`account_asset.py`), vistas y seguridad de 19, `stock_account` en
  `depends`, `auto_install: False`.
- Correcciones surgidas de las revisiones (ver `STATE.md`): nota de crédito en cero, publicar varias
  facturas, asiento manual de donación (`is_donation` editable, partner en
  borrador, diario con hash, sin sufijo), "Crear factura" oculto, `_logger`
  sin usar y traducción `es_VE` regenerada.

**Fuera**
- La donación por scrap (`stock.scrap`): modelo, vistas, secuencia
  `stock.donation`, razones en etiquetas.
- Las migraciones `19.0.2.0.3` (scrap → etiquetas) y `17.0.1.0.5`: el cliente
  que migra entra con saldos iniciales y base nueva.
- `create_invoice`/`create_multi_invoice` de V19: #1440 no factura las
  donaciones de picking sin pedido.
- Los módulos propios de cada cliente (por ejemplo, el que agrega paciente y médico
  a las donaciones).
- Cambios en `l10n_ve_stock_account` e integra-addons (ver Riesgos).

## Approach

Ver `design.md`.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| `binaural_subsidiary_stock` (integra) sobrescribe `_create_account_move` sin `super` y lee `stock.scrap.is_donation` | No se instala en el cliente que migra; queda documentado en el informe a Producto |
| `binaural_stock_dispatch_note` deja el contacto del picking solo lectura si `is_donation` y el registro existe | Cambio acompañante de 1 línea en integra-addons (`is_donation and sale_id`) |
| `l10n_ve_inventory_book` (tests) espera 'Autoconsumo' en donaciones | Ajustar `test_outgoing_with_donation` en integra |
| El módulo V19 (`19.0.2.0.6`) está instalado como dependencia de `binaural_operative` en clientes 19; si el cambio llegara a `maintenance-19.0` llegaría a todos con su próxima actualización (pierde la donación por scrap, sin migración) | El cambio va a `19.0` (tronco): solo llega con el siguiente corte de mantenimiento |
| El módulo propio del cliente en 17 usa campos y comportamientos que cambian: restaura al donante después de publicar, `test_22` espera el sufijo `- <ref>`, y una línea sin donante ahora aparece con el partner de la compañía | Se ajusta al migrar ese módulo (fuera de este módulo) |
| Producto aún debe validar el contacto libre en el pedido de donación | Pendiente con Producto |

## Criterios de aceptación

- [x] El módulo instala en Odoo 19 con sus dependientes (`binaural_operative`, `binaural_stock_dispatch_note`, `l10n_ve_inventory_book`).
- [x] La suite de `l10n_ve_donation` pasa en una base nueva (185 tests con las donaciones recibidas).
- [x] Flujos de `STATE.md` recorridos en la interfaz (picking, pedido con factura y nota de crédito, asiento manual, certificado).
- [ ] Cambios acompañantes en integra-addons (`binaural_stock_dispatch_note`, `l10n_ve_inventory_book`), fuera de este módulo.
