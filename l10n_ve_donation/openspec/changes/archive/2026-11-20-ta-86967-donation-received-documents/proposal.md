# Proposal: donaciones recibidas y documentos estandarizados en `l10n_ve_donation` 19

## Metadata

| Campo | Valor |
|---|---|
| Change ID | `ta-86967-donation-received-documents` |
| Tarea | [Tarea 86967](https://binaural.odoo.com/odoo/project.task/86967) |
| Tipo | REF / FEAT |
| Estado | Implementado |
| Módulo destino | `l10n_ve_donation` |
| Owner | Roger Vera |
| Rama base | `19.0` |
| Origen | Módulo propio de un cliente en 17 (tickets 15445, 15672, 86707) |

## Contexto

`l10n_ve_donation` solo modelaba donaciones **otorgadas** por la compañía. Un
cliente en Odoo 17 recibe donaciones y las resolvió en un módulo propio:
certificado al donante, recepción de mercancía validada, cuentas de ingresos y un
Recibo al paciente. Al migrarlo a 19 se lleva al módulo compartido lo que no es
propio del cliente.

## Situación actual → esperada

| Situación | Hoy (antes del change) | Esperado |
|---|---|---|
| Donación recibida en dinero | Sin modelo: se resolvía en un módulo de cliente | Asiento manual con el donante en cada línea; Certificado de Donación |
| Recepción de mercancía | Sin donante, sin asiento marcado, sin documento | Donante obligatorio, asiento marcado como donación recibida y Certificado desde el picking |
| Venta de donación en USD | La nota de crédito automática sale en bolívares (100 Bs por una factura de 100 USD) y la factura queda por cobrar | La nota sale en la moneda de la factura y la deja revertida |
| Documentos | RIF «21232157-1», dirección solo con la calle, números «5000.00», certificado en A4 | RIF «J-21232157-1», dirección completa, formato venezolano, certificado en carta |
| Grupo Gestor de Donaciones | Se pierde al guardar la ficha del usuario | Privilegio propio, independiente del de Contabilidad |
| Donación por extracto bancario | El asiento no queda como donación ni ofrece certificado | Se marca solo y la marca se quita si se deshace la conciliación |

## Decisiones

| Tema | Decisión |
|---|---|
| Dónde vive | Dentro de `l10n_ve_donation`; inerte sin cuentas de donaciones recibidas |
| Dirección | Por cuentas de ingresos de la compañía (solo asientos manuales), como en 17 |
| Contactos de las líneas | Recibidas: el donante en cada línea. Otorgadas: sin cambio (compañía en las líneas, beneficiario en la cabecera) |
| Documentos | Certificado = recepción (donante); Recibo = entrega (beneficiario); en dinero y mercancía |
| Recibo | Estructura del recibo de 17 sin paciente; reemplaza la redacción de acta de los documentos de otorgadas |
| Se queda en el módulo del cliente | Paciente/médico/diagnóstico, texto legal propio del cliente, forma de pago/banco/referencia (se debate después), `num2words`, migración 17.0.1.0.8 |

## Alcance

- Recibo de donación estandarizado (asiento y entrega), media carta, con puntos de
  extensión (`donation_receipt_beneficiary_extra`, `donation_receipt_legal`).
- `donation_income_account_ids`, `_is_incoming_donation`/`is_incoming_donation`.
- Líneas con el donante y validación al publicar (`_check_incoming_donation_before_post`).
- Certificado de donación recibida en dinero y en mercancía, con puntos de extensión
  (`donation_certificate_legal`, `donation_certificate_extra`).
- Recepción de mercancía: donante obligatorio, configuración contable con
  `valuation_account_id` y guarda en las entregas.
- Monto en bolívares primero y tasa según la moneda de la compañía (change
  `ta-86967-donation-module-1440-port`).
- Beneficiario (cabecera) de las donaciones otorgadas en dinero y guardas de impresión.
- Texto fuente en inglés con `es_VE.po`, como el resto de los `l10n_ve_*`.
- Ajustes de la validación funcional de Producto (19/11/2026): cuentas de gasto de donaciones,
  asiento de la recepción marcado, donación por extracto bancario, formato de los documentos,
  nota de crédito en moneda extranjera, privilegio del Gestor, comprobación en el servidor del
  reverso y del paso a borrador, y el Certificado en carta (REQ-DON-029 a 034).

## Fuera de alcance

Forma de pago/banco/referencia, pestaña Paciente/Médico, texto legal propio del cliente,
el port del módulo propio del cliente a 19.

Las decisiones C1 a C6 del informe de validación son de Producto y Contabilidad, y las mejoras
que salen de ellas no entran: el retiro de inventario con IVA y Libro de Ventas (C4) y el valor
documentado de la mercancía recibida (C6). Tampoco entran los textos en inglés de otros módulos
(H8) ni la lectura del costo alterno sin permisos elevados de `binaural_foreign_cost` (H13).

## Riesgos

- Redacción del Certificado y del Recibo genéricos: Producto debe validarla.
- Compañía con moneda base en USD en 19: se probó el cálculo con compañía en bolívares y en USD
  (a nivel del helper, no renderizando el documento de una compañía en USD).
- Una recepción mezclada (productos con y sin valoración automatizada) toma el equivalente
  por la tasa guardada del primer asiento de valoración publicado, aplicada al total.
- La recepción de punta a punta con un producto `real_time` queda cubierta por un test
  contra el core 19 (crédito = cuenta de la ubicación de origen).

## Criterios de aceptación

- [x] Una donación recibida en dinero o en mercancía emite su Certificado con el donante; sin
      cuentas de donaciones recibidas el módulo se comporta como antes.
- [x] La nota de crédito de una venta de donación en USD queda en USD y deja la factura revertida.
- [x] Los documentos muestran el RIF con prefijo, la dirección completa y los montos con formato
      venezolano; el Certificado sale en carta y el Recibo en media carta.
- [x] El asiento de valoración de una recepción queda marcado y solo el Gestor lo revierte, también
      si lo intenta desde la lista o por una llamada.
- [x] El asiento de un extracto conciliado contra una cuenta de recibidas se marca solo y se
      desmarca al deshacer la conciliación, sin bloquearla.
- [x] El Gestor de Donaciones se puede asignar sin modo desarrollador y no se pierde al guardar la
      ficha del usuario; las bases ya instaladas se actualizan con la migración `19.0.3.0.1`.
- [x] La suite del módulo pasa y cada requisito tiene un test que lo cita (ver `STATE.md`).

