# Feat: Validar productos y monto de una Nota de Crédito contra su factura origen

## Why

Ticket Helpdesk #13965. Hoy no existe ninguna restricción en `l10n_ve_invoice`
que ligue las líneas de una Nota de Crédito (`out_refund`/`in_refund`) con lo
facturado en el documento que revierte (`reversed_entry_id`). Un usuario puede:

- Agregar a la NC un producto que la factura original nunca tuvo.
- Acreditar, para un producto dado, un monto mayor al que se facturó por ese
  mismo producto.

Ambos casos generan una NC que no corresponde con la factura que dice
originarla, lo cual es un riesgo fiscal/contable para la localización
venezolana.

## What Changes

- Nuevo `@api.constrains` `_check_refund_against_origin` en `account.move`
  (`models/account_move.py`): para toda NC con `reversed_entry_id`, agrupa las
  líneas de producto por `product_id` (tanto de la NC como de la factura
  origen) y valida:
  1. Todo producto de la NC debe existir entre los productos de la factura
     origen.
  2. El monto acreditado acumulado por producto no puede superar el monto
     facturado por ese producto en el origen (comparación con
     `float_compare` y la precisión de la moneda del documento).
- Réplica del mismo chequeo en `account.move.line`
  (`models/account_move_line.py`, nuevo) sobre `product_id`, `price_unit`,
  `quantity`, `discount`: un `write()` directo sobre la línea no dispara el
  `constrains` del padre definido sobre `invoice_line_ids`.
- Mecanismo de excepción: la clave de contexto
  `l10n_ve_skip_refund_origin_validation` (ya prevista y documentada de
  antemano en `l10n_ve_exchange_difference`, hasta ahora un no-op) hace que
  la validación se salte por completo. Pensada para módulos que generan NC de
  forma automática con un producto propio, no para exponerse en UI.
- `l10n_ve_donation` (`models/account_move.py`, `_reverse_moves`) pasa ahora
  ese mismo flag al crear su NC de donación, porque usa un producto dedicado
  (`is_donation_product`) que nunca es el de la factura original.

## Módulos revisados por posible conflicto

- `l10n_ve_exchange_difference`: crea NC de diferencial cambiario con un
  producto dedicado. Ya pasaba el flag de bypass de forma anticipada en los
  dos puntos donde crea/postea la nota (`account_move_line.py:697,745`,
  `account_move.py:475`) — sin cambios necesarios.
- `l10n_ve_donation`: creaba NC con producto de donación sin el flag — se
  agregó (ver arriba). Regresión evitada.
- `integra-addons` (repo de cliente, `binaural_19/src/integra-addons`): sin
  hallazgos. `binaural_commissions`, `binaural_stock_landed_foreign_costs` y
  `binaural_pos_commissions` solo leen `move_type`/`reversed_entry_id`;
  `set_reversed()` en `binaural_commissions` vincula un move ya existente
  por `ref`, no crea una NC nueva. Ninguno requiere el bypass.
- Resto de módulos de `odoo-venezuela`: no se encontró ningún otro punto que
  cree `account.move` con `move_type` `out_refund`/`in_refund` de forma
  programática.

## Non-goals

- No se valida Nota de Débito (`debit_origin_id`): el ticket 13965 solo pide
  Notas de Crédito. El caso de ND queda fuera de alcance (ver ticket 13911 /
  hallazgos de review para ese caso).
