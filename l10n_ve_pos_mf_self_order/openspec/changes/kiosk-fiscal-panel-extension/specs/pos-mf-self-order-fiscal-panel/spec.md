# Spec delta: pos-mf-self-order-fiscal-panel

## ADDED Requirements

### Requirement: El módulo fiscal extiende el panel del Kiosko, no lo duplica

El sistema SHALL añadir el estado fiscal y las acciones de máquina fiscal como
**extensión** del panel de órdenes de base (`KioskOrdersDialog`), mediante patch
de componente y `t-inherit` de plantilla, sin re-implementar el panel. Cuando
`l10n_ve_pos_mf_self_order` está instalado, el panel de base SHALL mostrar los
estados `pending_fiscal` y `complete` y los botones **Imprimir factura fiscal** y
**Reimprimir copia**, además de la acción base **Crear factura**.

#### Scenario: Panel con máquina fiscal muestra estado y acción fiscal

- **GIVEN** un Kiosko con el módulo fiscal instalado y una orden facturada sin
  número fiscal (`pending_fiscal`)
- **WHEN** el operador la selecciona en el panel de órdenes
- **THEN** ve el estado "pendiente de imprimir en la máquina fiscal" y el botón
  "Imprimir factura fiscal"; al imprimir, la orden pasa a `complete` y el botón
  cambia a "Reimprimir copia"

#### Scenario: Reparto de responsabilidades

- **GIVEN** el conjunto base + fiscal instalado
- **WHEN** se revisa dónde vive cada pieza
- **THEN** listar órdenes, crear factura y los reintentos de cola están en base;
  el número fiscal, la impresión/reimpresión y el estado fiscal están en el
  módulo fiscal, enganchados por extensión

### Requirement: El shell de debug incorpora las herramientas de máquina fiscal por extensión

El sistema SHALL añadir al shell de debug de base (`KioskDebugDialog`) el badge de
estado de conexión y los botones **Comprobar estado de conexión** y **Parear
máquina fiscal**, mediante extensión, sin un segundo botón flotante propio.

#### Scenario: Debug con herramientas fiscales

- **GIVEN** un Kiosko con el módulo fiscal instalado, en modo debug
- **WHEN** el operador abre el shell de debug desde el único botón flotante
- **THEN** ve, además de "Ver órdenes" y los reintentos de cola, el estado de la
  máquina fiscal (última prueba) y los botones para comprobar la conexión y
  parear el puerto
