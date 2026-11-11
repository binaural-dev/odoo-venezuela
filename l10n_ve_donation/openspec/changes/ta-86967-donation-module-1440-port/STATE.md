# STATE — estado real de la verificación (2026-11-11)

## Origen

Pedido del usuario: "la lógica de #1440 debe SUSTITUIR POR COMPLETO al
`l10n_ve_donation` actual de V19 (ni extensión ni parche encima)", con el
scrap fuera de alcance. Tarea: [Migración HIGEA v19 (86967)](https://binaural.odoo.com/odoo/project.task/86967).
Trabajo en la rama `19.0_feat-ta_86967_donation_module_1440_port`
(13 commits sobre `19.0`, `4a302c6ae`; salió de `maintenance-19.0` y se rebasó sobre
`19.0`, que la contiene entera, sin conflictos). Sin push ni PR todavía.

## Comando exacto

```bash
cd /home/rogerdev/binaural/docker-odoo
./odoo test donation-19.0 l10n_ve_donation
scripts/precommit donation-19.0 -m l10n_ve_donation
```

Instancia temporal `donation-19.0` (puerto 8095; `instances.json` local, no
versionado): `src/enterprise-19.0`, el clon de odoo-venezuela de la rama,
`integra-addons` y `third-party-addons` 19 de `src/custom/monfarmacia`. Base
nueva por corrida.

## Resultado: suite de `l10n_ve_donation`

**130 tests, 0 fallos, 0 errores** (`post_install`, `-at_install`). Pre-commit
(`.po`, pylint opcional y obligatorio): pasa. Se corrió sobre el estado final;
los estados intermedios de los commits no se corrieron uno a uno.

| Archivo | Tests | REQ-ID | Estado |
|---|---|---|---|
| `test_stock_picking.py` | 26 | 001, 002, 003, 004, 006, 007, 015, 017 | PASS |
| `test_stock_move.py` | 12 | 005, 016 | PASS |
| `test_stock_location.py` | 13 | 009 | PASS |
| `test_stock_picking_type.py` | 6 | 008 | PASS |
| `test_stock_return_picking.py` | 6 | 007 | PASS |
| `test_product_warehouse.py` | 6 | 010 | PASS |
| `test_sale_order.py` | 8 | 011 | PASS |
| `test_sale_account_move.py` | 37 | 011, 012, 013, 014, 016 | PASS |
| `test_donation_credit_note_regression.py` | 6 | 012, 013 | PASS |
| `test_coverage_gaps.py` | 5 | varios | PASS |
| `test_account_asset.py` | 5 (de V19) | baja de activos | PASS |

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

Base `donation_ui` de la instancia `donation-19.0` (datos sintéticos: VEF/USD con tasa 380, almacén y ubicación de donación, producto con valoración `real_time`, beneficiario).

| Flujo | Resultado |
|---|---|
| Picking desde el menú Donaciones | El tipo de operación solo ofrece el de donación; motivo 'Donación' en solo lectura; validar sin contacto ni motivo da el error esperado; validado, genera el asiento (`is_donation`, referencia = picking, apuntes con el partner de la compañía, cabecera = beneficiario) |
| Certificado de entrega | 3 unidades × 15,00 = 45,00, igual al valor del movimiento; sale en español |
| "Crear factura" en el picking validado | Aparecía; tras el cambio ya no sale |
| Pedido de donación → factura → confirmar | Un solo asistente de alerta publica la factura y su nota de crédito. Antes de corregir, la nota salía en **0,00** sin impuesto ni línea por cobrar; ahora `INV/2026/0003` (0,79 + 0,13 = 0,92) queda `reversed` y la nota `INV/2026/0004` copia base, impuesto y total |
| Asiento manual de donación | `is_donation` visible y editable en un asiento nuevo; al registrar, los apuntes quedan con el partner de la compañía; un asiento creado por RPC con `partner_id: False` también |

## Hallazgos de la revisión de código (binaural-fn-programador:code-reviewer, sin publicar)

| Id | Hallazgo | Estado |
|---|---|---|
| B1 | Alcance: la rama sustituye un módulo compartido; en `maintenance-19.0` llegaría a todo cliente 19 | ✅ el PR va a `19.0` (una tarea nace del tronco). El módulo V19 está instalado como dependencia de `binaural_operative` en bases 19 de prueba (sin donaciones registradas); hay al menos un cliente que usa donaciones (por identificar). Falta confirmar el calendario del corte de mantenimiento |
| I1 | Donaciones sin pedido con motivo 'Donación': efecto en guías de despacho y libro de inventario | ✅ guías: una donación no se lista (REQ-DON-017; el certificado de entrega las sustituye; con el tipo de entrega estándar sí aparecía). ✅ libro: la devolución de la entrega de un pedido de donación ya no hereda el motivo 'Donación' (REQ-DON-007), así que no cuenta como retiro. Sigue por reportar al Libro de Inventario que su condición de retiros no mira la dirección del movimiento. Por decidir con Producto: si se bloquean también las devoluciones de pedidos de donación (hoy se permiten, como en el pin; el 19 original no tenía regla) |
| I2 | "Crear factura" visible en donación sin pedido | ✅ corregido (REQ-DON-015) |
| I3 | Almacén por defecto del pedido | ✅ sin cambio: `sale_order.py` es idéntico al pin (17) |
| I4 | ACL de `account.move` para Donation Manager | ✅ se mantiene como en 17: el permiso es necesario para que quien factura una donación desde ventas cree la factura y su nota de crédito automática |
| I5 | `action_post` con varias facturas | ✅ corregido (REQ-DON-012) |
| I6 | Asientos manuales en diarios con hash | ✅ confirmado y corregido (REQ-DON-014) |
| I7 | Reversión de un lote mixto ignora las que no son donación | ✅ corregido (REQ-DON-013) |
| M1 | Documentos del openspec desactualizados | ✅ este commit |
| M2 | `es_VE.po` sin regenerar | ✅ regenerado |
| M3 | Commits intermedios con la suite en rojo | ✅ los commits se reorganizaron; solo se corrió el estado final |
| M4 | `default_is_donation` filtrado al contexto marcaba asientos que no son de donación (el pin escribía `is_donation` de forma explícita) | ✅ corregido (REQ-DON-005) |
| M5 | Certificado: UdM de la línea contra la del producto | ⏳ |
| M6 | Almacén único sin `subsidiary_id` en el constraint | ✅ sin cambio: `binaural_subsidiary_stock` no valida el almacén de donación, la condición por sucursal es la única (viene del pin; la sucursal en donaciones se pidió en la tarea 68350) |
| M7 | `binaural_stock_dispatch_note` deja el contacto readonly | ⏳ PR en integra-addons |
| M8 | `_logger` sin usar | ✅ quitado |

Otros hallazgos de la revisión en la interfaz:
- El contacto del picking de donación queda de solo lectura tras el primer guardado (`binaural_stock_dispatch_note/views/stock_picking.xml:30`: `is_donation and id`). Correcto con pedido; sin pedido debe poder escribirse (= M7).
- Certificado del asiento: hablaba de "bienes" aunque el asiento manual es de dinero, y el botón salía también en el asiento de valoración de un picking (REQ-DON-016, corregido). Visto en la base `donation_config`: "la suma de 38.000,00 Bs.F, equivalente a $ 84,44 a la tasa BCV del día 12/11/2026, de 450,0000 VEF por USD" (monto solo numérico, tasa con 4 decimales). Se usa la tasa guardada en el asiento (la de su fecha), no la del día de impresión.
- Sin traducción: "Is Donation", "Donation Reason", el mensaje de validación y el certificado salían en inglés (resuelto con el `.po` regenerado).

## Dependientes (mismos addons, base nueva)

`./odoo test donation-19.0 binaural_operative,binaural_stock_dispatch_note,l10n_ve_inventory_book`
→ 77 tests, 0 fallos, 2 errores. Los 3 módulos **instalan** con el módulo sustituto.

| Test | Estado | Razón |
|---|---|---|
| `l10n_ve_inventory_book` `test_outgoing_with_donation` | ERROR | no hay tasa VEF del día al crear el pedido (`UserError: There is no rate assigned for VEF on 2026-11-11`). No llega a la aserción |
| `l10n_ve_inventory_book` `test_outgoing_with_sale` | ERROR | mismo error de tasa; no usa donación, es del entorno de ese test |

`test_outgoing_with_donation` espera 'Autoconsumo' (V19): con este módulo debe
esperar 'Donación' (PR aparte en integra-addons; hoy ni siquiera ejecuta la
aserción en ese entorno por la falta de tasa). `test_form_does_not_repeat_reason_fields`
(inventory_book) pasa tras corregir la duplicación de `sale_id` en la vista del picking.

## No verificado

- La baja de activos (`account_asset`) en la interfaz; solo cubierta por `test_account_asset.py`.
- Nota de crédito publicada a mano (borrador → publicar) en la interfaz; cubierta por tests.
- Almacén por defecto de un pedido normal con varios almacenes (I3): en la prueba solo hay un almacén normal.
- Prueba con `binaural_subsidiary_stock` instalado (Higea no lo tiene).
- Los estados intermedios de cada commit.

## Próximos pasos

- [x] Port del módulo, sus tests, i18n y openspec.
- [x] Pre-commit y revisión con el agente de Binaural (hallazgos en el chat, sin publicar).
- [x] Recorrido en la interfaz de los flujos principales.
- [x] Destino del PR decidido: `19.0` (rama rebasada y renombrada).
- [ ] Publicar la rama y abrir el PR (sin sección "Test plan").
- [ ] PR en integra-addons: `binaural_stock_dispatch_note` (contacto readonly solo con pedido) y `l10n_ve_inventory_book` (test espera 'Donación').
- [ ] Mensaje a Producto sobre `binaural_subsidiary_stock` (override de `_create_account_move` sin `super` y lectura de `stock.scrap.is_donation`).
- [ ] Ajustes en `higea_donation` al migrarlo (`test_22`, restauración del donante, líneas sin donante).
