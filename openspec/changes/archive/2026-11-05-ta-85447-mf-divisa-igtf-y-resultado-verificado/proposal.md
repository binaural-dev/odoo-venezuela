## Why

Tarea https://www.binauraldev.com/odoo/project/614/tasks/85447 (proyecto Integra 3.0, hito
"Mejoras Vertical Ventas 4to Trimestre").

**1. Código fiscal de divisa sin IGTF.** La máquina fiscal TFHKA separa los medios de pago
por código (manual HKA V8.5.0, págs. 22-24 y 81-83): 01-19 moneda nacional, 20-24 divisas.
Con el Flag 50 en `00` los códigos de divisa no se pueden cerrar, y con `01` la máquina cobra
un IGTF (3%). En Odoo, `code_fiscal_printer` (`l10n_ve_pos_mf`) es un Char libre y no sabe
nada de `apply_igtf` (`l10n_ve_pos_igtf`), así que se puede configurar un método 20-24 sin
IGTF. En un cliente (2026-10-24) los métodos de efectivo en USD tenían el código `20` sin
IGTF y toda venta en USD terminaba mal.

**2. Una falla de la máquina detenía o perdía la venta.** `l10n_ve_pos_mf` imprimía dentro
de `finalizeValidation` y devolvía `false` si fallaba. En Odoo 19 el core navega igual al
recibo (`shouldHideValidationBehindFeedbackScreen` solo se detiene ante un `RPCError`), o a
la pantalla de feedback y a la orden siguiente con la impresión automática. La orden
quedaba en borrador, sin sincronizar y fuera de "Pendientes por facturar". El PdV no debe
detenerse: la orden se sincroniza sin número y se imprime después.

**3. El driver reportaba error con la factura impresa.** Medido en la máquina de pruebas
(HKA80 Z7C7046254, ver `design.md`): si S1 no responde después del cierre, o si un comando
falla después del primer pago (el `7` de `abortTransaction` termina la factura como válida
en vez de anularla), el driver devuelve `success: false` aunque la máquina emitió una
factura válida. Cualquier reintento (PdV, factura del backend, Kiosko) emite **otra**, y con
el punto 2 el pedido quedaría "pendiente" a un clic de duplicarse.

## What Changes

1. **Restricción en `pos.payment.method`:** un código 20-24 exige `apply_igtf`. Sin
   `l10n_ve_pos_igtf` instalado ningún método puede tenerlo. `@api.constrains` con un
   callable para no depender del módulo.
2. **`get_data_invoice`** devuelve `valid: false` si un pago usa un método 20-24 sin IGTF,
   antes de hablar con la máquina. Help de `code_fiscal_printer` corregido.
3. **Driver (`l10n_ve_mf_base`): resultado verificado.** `printInvoice`, `printCreditNote` y
   `printDebitNote` toman una foto de S1 (número del documento, "Subtotal de Ventas", Z y
   serial) antes de abrir el documento. Un éxito se devuelve igual que antes. Si la
   impresión falla, el driver averigua con la máquina qué quedó emitido y devuelve:
   - `success: true, printed: true, recovered: true` con el número, si quedó válido;
   - `success: false, printed: false`, si no se emitió o salió anulado (se puede reimprimir);
     sin ningún pago enviado no hace falta consultar nada;
   - `success: false, printed: null, reason, verification`, si no se pudo saber.
   Nuevo `verifyDocument(verification)` para resolverlo después.
4. **PdV (`l10n_ve_pos_mf`): la venta sigue.** Si la impresión falla, la orden se sincroniza
   sin número y queda en "Pendientes por facturar". Si el resultado es `printed: null`, queda
   además "por verificar" (`pos.order.mf_print_verification`) en el servidor y en una cola del
   navegador. Antes de imprimir cualquier documento (venta o pendiente), el PdV resuelve esa
   cola con `verifyDocument`: asigna el número, la pasa a pendiente normal o, si no se puede
   saber, avisa y la deja para revisión manual; si la máquina no responde, el documento nuevo
   queda pendiente. Un pedido por verificar nunca se reimprime, tampoco al volver a validarlo
   después de que el servidor rechazó la sincronización.
5. **Resolución manual:** asistente en el pedido (`pos.order.mf.verification.wizard`, gerente
   del PdV) con el número esperado, el serial y el Z sugeridos.
6. Traducciones es_VE. Tests Python y Hoot (driver y PdV).

## Non-goals

- **Leer el Flag 50 (S3) antes de imprimir.**
- **Activar `apply_igtf` solo (onchange)** al poner un código 20-24.
- **Editar `code_fiscal_printer` con sesiones abiertas** (`_is_write_forbidden`).
- **Volver fatal el `199`/`1XX`:** con Flag 50 = 00 y código 20 la máquina acepta el pago y
  rechaza el `199`; el driver devuelve el número correcto. Volverlo fatal crearía un
  duplicado (medido, `design.md`).
- **Factura del backend (`l10n_ve_account_mf`), Kiosko y Megasoft:** reciben las
  correcciones del driver (los dos casos de duplicado ahora devuelven la factura emitida) y
  un mensaje claro en el caso desconocido, pero no el flujo "por verificar". Seguimiento
  aparte.
- **Contradicción de los códigos 03/04** entre la vista de la caja y el help (viene de antes).

## Impact

- **Módulos:** `l10n_ve_mf_base` 19.0.1.1.3 → 19.0.1.2.0 (driver) y `l10n_ve_pos_mf`
  19.0.3.1.3 → 19.0.3.2.0 (restricción, PdV, campo, asistente, ACL del asistente para
  `point_of_sale.group_pos_manager`).
- **Todos los clientes con máquina fiscal:**
  - una lectura S1 más por documento: ~70 ms, hasta ~400 ms si la máquina termina de
    imprimir el ticket anterior (medido);
  - una falla de impresión ya no detiene la venta: la orden queda pendiente por facturar;
  - los casos de "impresa pero con error" devuelven la factura emitida en vez de error.
- **Despliegue:** la restricción no corre al actualizar. Antes de actualizar, correr la
  consulta de "Detección previa" (`design.md`) y corregir lo que aparezca.
