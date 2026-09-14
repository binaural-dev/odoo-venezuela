# Feat: Permitir productos tipo Servicio ajenos a la factura origen en Notas de Crédito

## Why

Tarea #81674. La constraint `_check_refund_against_origin` (agregada en el
cambio `l10n-ve-invoice-credit-note-origin-validation`, ticket #13965) bloquea
por igual cualquier producto de una Nota de Crédito que no esté en la factura
origen, sin distinguir su tipo. Eso es correcto para devoluciones de
inventario (Almacenable/Consumible), pero bloquea también conceptos
financieros que por naturaleza nunca figuran en la factura original: pronto
pago, descuento comercial, diferencial cambiario. Hoy el cliente necesita un
rodeo manual para emitir esas Notas de Crédito.

## What Changes

- `_check_refund_against_origin` (`models/account_move.py`): cuando un
  producto de la NC no está en la factura origen y es de tipo `service`, ya
  no se lanza `ValidationError` -- se hace `continue` y su monto se acumula
  aparte (`service_exempt_total`), en lugar de sumarse a `current_totals`.
  Almacenable/Consumible ajeno al origen sigue bloqueado exactamente igual
  que antes.
- Nuevo chequeo agregado, solo cuando `service_exempt_total > 0`: la suma de
  todo lo acreditado en la NC (productos normales + servicios exentos) más lo
  ya acreditado por Notas de Crédito hermanas no puede superar el total
  facturado en la factura origen (`origin_totals` sumado completo). Un
  servicio ajeno no tiene tope por producto (no hay nada en el origen contra
  qué compararlo), pero no puede dejar el monto sin control: se topa contra
  el total general en lugar de contra un producto puntual.
- Nueva traducción ES-VE para el mensaje de error del chequeo agregado.

## Non-goals

- No se crean los productos de servicio específicos (Pronto Pago, Descuento
  Comercial, Diferencial Cambiario) -- se asume que ya existen en el catálogo
  o se gestionan aparte.
- No se valida ni modifica cuentas contables, impuestos o el asiento
  generado por estos productos de servicio -- se asume que su ficha ya está
  correctamente configurada.
- No se migra ningún dato existente; el cambio rige hacia adelante.
