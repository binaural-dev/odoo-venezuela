# Spec delta: pos-self-order-kiosk-orders-panel

## ADDED Requirements

### Requirement: Panel de órdenes del Kiosko en base, funcional sin máquina fiscal

El sistema SHALL ofrecer, en `l10n_ve_pos_self_order`, un panel de órdenes del
Kiosko que liste las órdenes de la caja (paid/done/invoiced, con líneas) cargadas
del servidor y permita **crear la factura** de una orden pagada pendiente de
facturar. El panel SHALL funcionar con independencia de que el módulo de máquina
fiscal esté instalado. Los datos SHALL venir de una ruta pública
(`/l10n_ve_pos_self_order/kiosk/session_orders`) validada por `access_token`, en
el formato que consume `connectNewData`, sin pedir campos fiscales.

#### Scenario: Kiosko sin máquina fiscal recupera una factura

- **GIVEN** un Kiosko con `l10n_ve_pos_self_order` pero SIN
  `l10n_ve_pos_mf_self_order`, y una orden pagada pendiente de facturar
- **WHEN** el operador abre el panel de órdenes en modo debug y pulsa "Crear
  factura" sobre esa orden
- **THEN** el panel llama al endpoint `create_invoice`, la orden queda facturada
  y el panel refleja el nuevo estado, sin depender de ninguna lógica fiscal

#### Scenario: El estado "facturada" se deriva del servidor

- **GIVEN** una orden cargada desde `session_orders`
- **WHEN** el panel calcula su estado
- **THEN** la considera facturada cuando `state === "invoiced"` (señal
  autoritativa del servidor), no a partir de un flag client-side que puede no
  venir en órdenes cargadas del servidor

### Requirement: Shell de debug del Kiosko con acceso único, extensible

El sistema SHALL exponer un botón flotante de debug (visible solo con `?debug=1`)
que abra un shell de debug del Kiosko con: abrir el panel de órdenes y reintentar
el registro de órdenes de la cola durable (pendientes y fallidas). El shell SHALL
ser un único punto de entrada, extensible por otros módulos (p. ej. el fiscal
añade sus herramientas de máquina fiscal) sin agregar un segundo botón.

#### Scenario: Un solo botón de debug aunque haya módulo fiscal

- **GIVEN** un Kiosko con el módulo fiscal instalado, en modo debug
- **WHEN** el operador ve la raíz del Kiosko
- **THEN** hay UN solo botón de debug; al abrirlo, el shell muestra tanto las
  herramientas de base (órdenes, reintentos de cola) como las fiscales añadidas
  por extensión
