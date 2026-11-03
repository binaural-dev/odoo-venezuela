## Why

Ticket https://binaural.odoo.com/odoo/helpdesk/action-389/16119: el TXT de retenciones de IVA del
SENIAT solo incluía los comprobantes de facturas de proveedor. Los de notas de crédito de proveedor
(`type = in_refund`) quedaban fuera aunque estuvieran emitidos y dentro del período. En septiembre de
2026 salían 317 comprobantes de facturas y faltaban 3 de notas de crédito (NC 1691, 1688 y NC122937).

La causa es que el wizard (`generate_txt`, que valida con `search_count`) y el controlador
(`download_retention_iva_txt`, que escribe el archivo) filtraban por `("type", "=", "in_invoice")`.
`_retention_iva()` ya mapeaba `in_refund` a tipo de documento `03` y tomaba el documento afectado de
`reversed_entry_id`; solo faltaba la búsqueda. La exclusión de `in_refund` en el spec salió de la
línea base documental (tarea 80531), que describió lo que hacía el código, no un requisito de negocio.

## What Changes

- `wizard.retention.iva._get_retention_iva_domain()`: dominio único con `type in (in_invoice, in_refund)`,
  usado por `generate_txt` (conteo) y por el controlador (descarga), para que no vuelvan a diferir.
- Si el período solo tiene retenciones de notas de crédito, el wizard genera el archivo y no lanza
  "No retentions found".
- `_retention_iva()`: se quita una asignación duplicada de "Número del documento afectado" que
  sobrescribía la anterior y dejaba `False` (el TXT escribía "False") en notas de débito sin origen;
  ahora sale `0`.
- `_retention_iva()`: el número de control vacío sale como cadena vacía; antes la descarga fallaba con
  `TypeError` al concatenar `False` (el sistema permite publicar una NC sin número de control).
- Las notas de débito no cambian: su comprobante es `in_invoice` y se reconocen por `journal_id.is_debit`.

## Impact

- **Módulo tocado:** `l10n_ve_payment_extension` (19.0.2.2.5 → 19.0.2.2.6).
- **Despliegue:** `-u l10n_ve_payment_extension`. Sin cambio de esquema ni de vistas.
- **Efecto:** el TXT de un período con notas de crédito trae filas nuevas (tipo `03`); las de facturas
  salen igual que antes.
- **Spec:** requisito "Exportación TXT de retenciones IVA para el SENIAT" actualizado; los escenarios
  "solo notas de crédito" pasaron de error a archivo generado.
- **Fuera de alcance:** la retención de una NC no se puede aprobar si su saldo es 0 (regla existente,
  la NC se concilia con su factura al publicarse); `in_debit` no se incluye porque la retención de una
  nota de débito se guarda como `in_invoice`.
