# Proposal: donaciones recibidas y documentos estandarizados en `l10n_ve_donation` 19

## Metadata

| Campo | Valor |
|---|---|
| Change ID | `ta-86967-donation-received-documents` |
| Tarea | [Migración HIGEA v19 (86967)](https://binaural.odoo.com/odoo/project.task/86967) |
| Tipo | REF / FEAT |
| Estado | Implementado |
| Módulo destino | `l10n_ve_donation` |
| Origen | `higea_donation` 17 (tickets 15445, 15672, 86707) |

## Contexto

`l10n_ve_donation` solo modelaba donaciones **otorgadas** por la compañía. Higea
(Odoo 17) recibe donaciones y las resolvió en su custom `higea_donation`:
certificado al donante, recepción de mercancía validada, cuentas de ingresos y un
Recibo al paciente. Al migrar Higea a 19 se lleva al módulo compartido lo que no es
propio del cliente.

## Decisiones

| Tema | Decisión |
|---|---|
| Dónde vive | Dentro de `l10n_ve_donation`; inerte sin cuentas de donaciones recibidas |
| Dirección | Por cuentas de ingresos de la compañía (solo asientos manuales), como Higea |
| Contactos de las líneas | Recibidas: el donante en cada línea. Otorgadas: sin cambio (compañía en las líneas, beneficiario en la cabecera) |
| Documentos | Certificado = recepción (donante); Recibo = entrega (beneficiario); en dinero y mercancía |
| Recibo | Estructura del recibo de Higea sin paciente; reemplaza la redacción de acta de los documentos de otorgadas |
| Se queda en `higea_donation` | Paciente/médico/diagnóstico, texto legal del Voluntariado, forma de pago/banco/referencia (se debate después), `num2words`, migración 17.0.1.0.8 |

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

## Fuera de alcance

Forma de pago/banco/referencia, pestaña Paciente/Médico, texto legal del Voluntariado,
el port de `higea_donation` a 19.

## Riesgos

- Redacción del Certificado y del Recibo genéricos: Producto debe validarla.
- Moneda base de Higea en 19: se probó el cálculo con compañía en bolívares y en USD
  (a nivel del helper, no renderizando el documento de una compañía en USD).
- Una recepción mezclada (productos con y sin valoración automatizada) toma el equivalente
  por la tasa guardada del primer asiento de valoración publicado, aplicada al total.
- La recepción de punta a punta con un producto `real_time` queda cubierta por un test
  contra el core 19 (crédito = cuenta de la ubicación de origen).
