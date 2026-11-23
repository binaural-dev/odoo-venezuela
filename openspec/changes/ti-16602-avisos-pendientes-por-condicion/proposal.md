## Why

En las facturas de proveedor el aviso "Tiene débitos pendientes…" aparece dos veces (el de IGTF y el estándar), y los avisos de "tasa tomada de la orden" de compra y de venta no se ven (ticket #16602, detectado en el staging de un cliente).

`account.view_move_form` tiene cuatro avisos `alert alert-info` hermanos, uno por tipo de documento (`out_invoice/out_receipt`, `in_invoice/in_receipt`, `out_refund`, `in_refund`). `l10n_ve_igtf` los reemplazaba por posición (`[1]`, `[2]`, `[3]` y otra vez `[3]`), y `l10n_ve_igtf_note_debit` ubicaba su aviso después de `[3]`. Cualquier `alert-info` que otro módulo agregue antes, en el mismo nivel, corre las posiciones.

La regresión sale de la combinación de cuatro cambios:

| Fecha | Commit | Cambio | Efecto |
|---|---|---|---|
| 2026-04-06 | `70aa860ab` | `l10n_ve_igtf` reemplaza los avisos con `//div[@class='alert alert-info'][N]`, con el `[3]` repetido | Desde aquí, en todos los clientes: la nota de crédito de proveedor tiene el aviso duplicado y la de cliente no tiene aviso de pendientes |
| 2026-05-25 | `7c4e9abfe` | `@class='alert alert-info'` (match exacto) pasa a `hasclass('alert', 'alert-info')` | También coinciden divs con más clases (`alert alert-info mb-0`) |
| 2026-08-29 | `b7faadcd4` | `l10n_ve_igtf_note_debit` ubica su aviso con `alert-info')][3]` | El aviso de notas de débito se mueve junto con la posición 3 |
| 2026-11-02 | `3544aa987`, `ec541e29d` (#16148) | `l10n_ve_sale` y `binaural_purchase` agregan un aviso de tasa `alert alert-info mb-0` después de `//header` | Disparador: los avisos de tasa ocupan las posiciones 1 y 2, IGTF los reemplaza (desaparecen) y la factura de proveedor queda con el aviso duplicado |

Formulario resultante antes del cambio:

| Escenario | out_invoice | in_invoice | out_refund | in_refund | Avisos de tasa |
|---|---|---|---|---|---|
| Sin módulos que agreguen avisos | IGTF | IGTF | ninguno | duplicado | — |
| Con `binaural_purchase` y `l10n_ve_sale` | IGTF | duplicado | solo el estándar | duplicado | ocultos |

## What Changes

- `l10n_ve_igtf`: los cuatro reemplazos ubican cada aviso por su condición (`invoice_has_outstanding` y el `move_type` de su `invisible`), no por posición. Se corrige así también el `[3]` repetido. El contenido de los avisos no cambia, así que las traducciones siguen valiendo.
- `l10n_ve_igtf_note_debit`: el aviso "You have pending IGTF notes to pay" se ancla después del aviso de pendientes de `in_refund`, el último de los cuatro.
- Prueba `test_move_form_outstanding_alerts` en `l10n_ve_igtf`: verifica un único aviso IGTF por tipo, con y sin un módulo que agregue un `alert-info` antes que IGTF.

## Impact

- **Specs afectadas**: `l10n_ve_igtf` y `l10n_ve_igtf_note_debit` (requisitos nuevos sobre los avisos del formulario).
- **Código**: `l10n_ve_igtf/views/account_move.xml` y `l10n_ve_igtf_note_debit/views/account_move_views.xml`. Versiones 19.0.1.2.23 y 19.0.1.0.3. Solo vistas, sin migración.
- **Clientes**: todos los de la 19.0 con `l10n_ve_igtf` (50 repos de cliente). En 45 están también `binaural_purchase` y `l10n_ve_sale`, y en 5 solo `binaural_purchase`.
- **Qué ve el usuario después**:
  - factura de proveedor y nota de crédito de proveedor: un solo aviso;
  - nota de crédito de cliente: el aviso IGTF con anticipos;
  - los avisos de tasa de la orden de compra y de venta vuelven a verse;
  - el aviso de notas de débito IGTF queda siempre después de los avisos de pendientes.
- **Lo que no cambia**: cálculos, asientos, widgets de pago, datos y traducciones.
- **Riesgo**: si el core cambiara el texto del `invisible` de esos avisos, la xpath no encontraría su nodo y el `-u` fallaría al instalar. Es un fallo visible, no un aviso que desaparece en silencio.
- **Fuera de alcance**:
  - `//div[hasclass('d-flex')][2]` en la misma vista también es posicional; hoy funciona.
  - `binaural_advance_payment` (integra-addons) define una vista con el mismo xml id y el mismo campo de anticipos que IGTF.
