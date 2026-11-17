# STATE — estado de la verificación

## Origen

Pedido: "la lógica de #1440 debe SUSTITUIR POR COMPLETO al `l10n_ve_donation` actual de V19
(ni extensión ni parche encima)", con el scrap fuera de alcance. Tarea:
[Migración HIGEA v19 (86967)](https://binaural.odoo.com/odoo/project.task/86967).

## Comandos

```bash
cd docker-odoo
./odoo test <instancia> l10n_ve_donation
scripts/precommit <instancia> -m l10n_ve_donation
```

Instancia con `enterprise-19.0`, `odoo-venezuela`, `integra-addons` y `third-party-addons` 19,
base nueva por corrida.

## Resultado: suite de `l10n_ve_donation`

**185 tests, 0 fallos, 0 errores** en toda la suite del módulo (131 de la migración y 54 de las
donaciones recibidas, ver `ta-86967-donation-received-documents`); pre-commit (`.po`, pylint
opcional y obligatorio) pasa.

| Archivo | Tests | REQ-ID |
|---|---|---|
| `test_stock_picking.py` | 27 | 001, 002, 003, 004, 006, 007, 015, 017, 019 |
| `test_stock_move.py` | 12 | 005, 016 |
| `test_stock_location.py` | 13 | 009 |
| `test_stock_picking_type.py` | 6 | 008 |
| `test_stock_return_picking.py` | 6 | 007 |
| `test_product_warehouse.py` | 6 | 010 |
| `test_sale_order.py` | 8 | 011 |
| `test_sale_account_move.py` | 37 | 011, 012, 013, 014, 016, 026 |
| `test_donation_credit_note_regression.py` | 6 | 012, 013 |
| `test_coverage_gaps.py` | 5 | varios |
| `test_account_asset.py` | 5 (de V19) | baja de activos |
| `test_received_donation.py` | 54 | 018 a 028 |

Tests agregados tras la revisión (trazables a su REQ-ID):
- REQ-DON-013: `test_donation_credit_note_mirrors_the_invoice_amounts` (base, impuesto, total y líneas de la nota) y `test_reverse_moves_of_a_mixed_batch_reverses_every_invoice` (lote con una factura de donación y una normal).
- REQ-DON-012: `test_08b_post_several_donation_invoices_at_once`, `test_08c_post_mixed_batch_of_donation_invoice_and_entry`, `test_08d_post_again_does_not_reverse_a_posted_invoice_twice`.
- REQ-DON-014: `test_21_is_donation_is_editable_on_new_manual_entry`, `test_09a` a `test_09g` (partner en borrador, asiento ya existente, asiento normal, publicar sin escribir, líneas con `partner_id: False`, partner vaciado, diario con hash).
- REQ-DON-015: `test_create_invoice_button_is_hidden_on_a_donation_without_sale` (con control: la misma entrega sin la marca sí ofrece el botón).
- REQ-DON-007: `test_05` y `test_06` de `test_stock_return_picking.py` (la devolución de la entrega de un pedido de donación no conserva el motivo 'Donación'; la de una entrega normal sí conserva el suyo).
- REQ-DON-005: `test_08b` y `test_08c` de `test_stock_move.py` (un `default_is_donation` filtrado en el contexto no marca el asiento de una entrega que no es de donación; el de una donación sigue marcado).
- REQ-DON-017: `test_donation_delivery_is_not_listed_in_the_dispatch_guides` (tipo de entrega estándar; con control sin la marca).
- REQ-DON-016: `test_23b`, `test_23c` y `test_23d` (monto y tasa con el bolívar como moneda de la compañía, como moneda alterna y sin equivalente), y `test_22` a `test_24` de `test_sale_account_move.py` (suma numérica, equivalente y tasa con 4 decimales; sin monto alterno; asiento manual no es de valoración) y `test_10_valuation_entry_has_no_donation_certificate` de `test_stock_move.py` (botón/acción rechazados en el asiento de un picking).

Bugs que los tests destaparon y que ya están corregidos en el código:
- `stock.return.picking` sobrescribía `_create_returns` (17); en 19 es `_create_return`, así que el bloqueo de devoluciones nunca corría.
- El motivo 'Donación' no se asignaba a un picking nuevo: la base le da el motivo por defecto de su tipo de operación en `create` y el cómputo de los permitidos no puede sobrescribir un valor recibido. Se asigna también en `create`/`write`.
- La vista del picking duplicaba `sale_id` (el dependiente `l10n_ve_inventory_book` exige uno solo).
- Publicar un asiento de donación en un diario con hash fallaba (`You cannot edit the following fields: Label and Partner`): se escribía sobre el asiento ya publicado.

## Verificación en vivo (interfaz)

Base de pruebas (datos sintéticos: VEF/USD con tasa 380, almacén y ubicación de donación, producto con valoración `real_time`, beneficiario).

| Flujo | Resultado |
|---|---|
| Picking desde el menú Donaciones | El tipo de operación solo ofrece el de donación; motivo 'Donación' en solo lectura; validar sin contacto ni motivo da el error esperado; validado, genera el asiento (`is_donation`, referencia = picking, apuntes con el partner de la compañía, cabecera = beneficiario) |
| Documento de la entrega | 3 unidades × 15,00 = 45,00, igual al valor del movimiento; sale en español (hoy es el Recibo de donación) |
| "Crear factura" en el picking validado | Aparecía; tras el cambio ya no sale |
| Pedido de donación → factura → confirmar | Un solo asistente de alerta publica la factura y su nota de crédito. La factura (0,79 + 0,13 = 0,92) queda `reversed` y su nota de crédito copia base, impuesto y total |
| Asiento manual de donación | `is_donation` visible y editable en un asiento nuevo; al registrar, los apuntes quedan con el partner de la compañía; un asiento creado por RPC con `partner_id: False` también |

## Decisiones y límites conocidos

| Tema | Decisión / estado |
|---|---|
| Alcance: el módulo sustituye a uno compartido | Va a `19.0` (tronco): llega con el siguiente corte de mantenimiento. El módulo V19 está instalado como dependencia de `binaural_operative` en bases 19 de prueba, sin donaciones registradas |
| Guías de despacho y libro de inventario | Una donación no se lista en las guías (REQ-DON-017). La devolución de la entrega de un pedido de donación no hereda el motivo 'Donación', así que no cuenta como retiro (REQ-DON-007). El Libro de Inventario aún no mira la dirección del movimiento en su condición de retiros |
| Devoluciones de pedidos de donación | Se permiten, como en la versión 17; por decidir con Producto si se bloquean |
| "Crear factura" en una donación sin pedido | Oculto (REQ-DON-015) |
| Almacén por defecto del pedido | Sin cambio: `sale_order.py` es idéntico al de la versión 17 |
| ACL de `account.move` para Donation Manager | Se mantiene como en 17: es necesario para que quien factura una donación desde ventas cree la factura y su nota de crédito automática |
| `action_post` con varias facturas | Un asistente publica todas las facturas del lote y sus notas (REQ-DON-012) |
| Asientos manuales en diarios con hash | Publicar no escribe sobre el asiento (REQ-DON-014) |
| Reversión de un lote mixto | Reversa también las facturas que no son de donación (REQ-DON-013) |
| `default_is_donation` filtrado al contexto | No marca los asientos que no son de donación (REQ-DON-005) |
| Certificado: UdM de la línea contra la del producto | Pendiente |
| Almacén único sin `subsidiary_id` en el constraint | Sin cambio: `binaural_subsidiary_stock` no valida el almacén de donación; la condición por sucursal es la única |
| `binaural_stock_dispatch_note` deja el contacto de solo lectura | Cambio en integra-addons: solo con pedido (`is_donation and sale_id`) |

Otros hallazgos de la verificación en la interfaz:
- El contacto del picking de donación queda de solo lectura tras el primer guardado (`binaural_stock_dispatch_note/views/stock_picking.xml`: `is_donation and id`). Correcto con pedido; sin pedido debe poder escribirse.
- El documento del asiento hablaba de "bienes" aunque el asiento manual es de dinero, y el botón salía también en el asiento de valoración de un picking (REQ-DON-016, corregido). Se usa la tasa guardada en el asiento (la de su fecha), no la del día de impresión.
- Sin traducción: "Is Donation", "Donation Reason", el mensaje de validación y el documento salían en inglés (resuelto con el `.po` regenerado).

## Seguimiento en otros módulos

- `binaural_stock_dispatch_note` y `l10n_ve_inventory_book` (integra-addons): ver `tasks.md`.
- `binaural_subsidiary_stock` (integra-addons): sobrescribe `_create_account_move` sin `super` y lee `stock.scrap.is_donation`.
- `higea_donation`: `test_22`, restauración del donante tras publicar y líneas sin donante, al migrarlo.

## No verificado

- La baja de activos (`account_asset`) en la interfaz; solo cubierta por `test_account_asset.py`.
- Nota de crédito publicada a mano (borrador → publicar) en la interfaz; cubierta por tests.
- Almacén por defecto de un pedido normal con varios almacenes: en la prueba solo hay un almacén normal.
- Prueba con `binaural_subsidiary_stock` instalado (Higea no lo tiene).
