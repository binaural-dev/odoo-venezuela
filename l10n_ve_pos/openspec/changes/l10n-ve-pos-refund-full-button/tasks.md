# Tasks

## 1. Implementación

- [x] 1.1 `ticket_screen.js`: `patch(TicketScreen.prototype, { onFullRefund() {...} })`
      usando la API pública de Odoo 19 (`getSelectedOrder`, `getOrderlines`,
      `getToRefundDetail`)
- [x] 1.2 `ticket_screen.xml`: botón "Reembolso total" insertado en la fila
      `control-buttons` vía xpath, mismo estilo que los botones nativos de
      esa fila

## 2. Verificación manual (confirmada en navegador, 2026-07-21)

- [x] 2.1 Botón "Reembolso total" aparece junto a "Details"/"Print Receipt"
      en el TicketScreen — confirmado por el usuario ("todo visualmente")
- [x] 2.2 Click en "Reembolso total" precarga cantidades correctamente —
      confirmado ("los reembolsos están funcionales")
- [ ] 2.3 Caso borde: orden con líneas ya parcialmente reembolsadas
      solo precarga el remanente — no confirmado explícitamente
- [x] 2.4 Pulsar "Refund" después crea la orden de reembolso normalmente
      — confirmado (flujo de reembolso funcional de punta a punta)
- [ ] 2.5 Caso borde: orden con un combo, líneas hijas consistentes con
      el padre — no confirmado explícitamente

## 3. OpenSpec

- [x] 3.1 `openspec validate --changes`
