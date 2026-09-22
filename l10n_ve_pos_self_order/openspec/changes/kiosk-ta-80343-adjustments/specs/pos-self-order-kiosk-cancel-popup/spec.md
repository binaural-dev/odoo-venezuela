# Spec delta: pos-self-order-kiosk-cancel-popup

## ADDED Requirements

### Requirement: Popup de cancelar orden en español

El popup nativo de cancelar orden del Kiosko (`pos_self_order.CancelPopup`)
SHALL mostrar el texto "¿Desea cancelar la orden?" y dos botones: "Sí" (confirma
la cancelación) y "No" (cierra el popup sin cancelar). La implementación SHALL
heredar el template del core (`t-inherit-mode="extension"`) sin reemplazarlo
por completo.

#### Scenario: Cliente abre el popup de cancelar

- **GIVEN** el cliente está en el carrito del Kiosko con al menos una línea
- **WHEN** toca "Cancelar orden"
- **THEN** ve el texto "¿Desea cancelar la orden?" con los botones "Sí" y "No"

#### Scenario: Confirmar cancelación

- **GIVEN** el popup de cancelar orden abierto
- **WHEN** el cliente toca "Sí"
- **THEN** la orden se cancela (mismo comportamiento que el core: `confirm()`)

#### Scenario: Descartar el popup

- **GIVEN** el popup de cancelar orden abierto
- **WHEN** el cliente toca "No"
- **THEN** el popup se cierra y la orden sigue intacta
