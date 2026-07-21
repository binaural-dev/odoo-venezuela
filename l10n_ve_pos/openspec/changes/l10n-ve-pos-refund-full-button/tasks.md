# Tasks

## 1. Implementación

- [x] 1.1 `ticket_screen.js`: `patch(TicketScreen.prototype, { onFullRefund() {...} })`
      usando la API pública de Odoo 19 (`getSelectedOrder`, `getOrderlines`,
      `getToRefundDetail`)
- [x] 1.2 `ticket_screen.xml`: botón "Reembolso total" insertado en la fila
      `control-buttons` vía xpath, mismo estilo que los botones nativos de
      esa fila

## 2. Verificación manual (pendiente — usuario prueba en navegador)

- [ ] 2.1 Abrir una orden sincronizada en el TicketScreen del PdV y
      confirmar que aparece el botón "Reembolso total" junto a
      "Details"/"Print Receipt"
- [ ] 2.2 Click en "Reembolso total": todas las líneas de la orden deben
      mostrar "To Refund: <cantidad total>" sin necesidad de
      seleccionarlas manualmente
- [ ] 2.3 Confirmar que una orden con líneas ya parcialmente reembolsadas
      solo precarga el remanente reembolsable, no la cantidad original
      completa
- [ ] 2.4 Confirmar que pulsar "Refund" después crea la orden de reembolso
      normalmente (mismo comportamiento que el flujo nativo hoy)
- [ ] 2.5 Probar con una orden que tenga un combo, verificando que las
      líneas hijas quedan consistentes con el padre

## 3. OpenSpec

- [x] 3.1 `openspec validate --changes`
