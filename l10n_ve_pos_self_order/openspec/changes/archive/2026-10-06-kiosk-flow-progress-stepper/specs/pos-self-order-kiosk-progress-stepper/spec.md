# Spec delta: pos-self-order-kiosk-progress-stepper

## ADDED Requirements

### Requirement: Barra de progreso de pasos en el Kiosko

El sistema SHALL mostrar en el Kiosko (`self_ordering_mode == 'kiosk'`) una barra
de progreso fija en la parte superior con los pasos del flujo de autopedido
(Identificación, Productos, Pago), resaltando el paso correspondiente a la
pantalla activa.

#### Scenario: El paso resaltado sigue a la pantalla activa

- **GIVEN** una caja en modo Kiosko con `l10n_ve_pos_self_order` instalado
- **WHEN** el cliente navega entre las pantallas del flujo (identificación →
  productos/carrito → pago)
- **THEN** la barra resalta el paso correspondiente (1 en `identification`; 2 en
  `product_list`/`product`/`combo_selection`/`cart`; 3 en `payment`), con los
  pasos previos marcados como completados

#### Scenario: La barra no aparece fuera del flujo de pedido

- **GIVEN** una caja en modo Kiosko
- **WHEN** la pantalla activa es la de bienvenida (`default`)
- **THEN** la barra de progreso no se muestra

#### Scenario: El modo móvil/QR no muestra la barra

- **GIVEN** una caja en `self_ordering_mode == 'mobile'` (QR)
- **WHEN** el cliente usa el autopedido
- **THEN** la barra de progreso de pasos no se muestra (es exclusiva del Kiosko)
