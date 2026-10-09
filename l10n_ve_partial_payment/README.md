# l10n_ve_partial_payment

Motor transversal de aplicación parcial de pagos, anticipos y conciliaciones
sobre `l10n_ve_igtf`. Este README se va llenando por tarea a medida que se
construye cada flujo — no reescribir lo ya cerrado de una tarea anterior al
avanzar con la siguiente, solo agregar su sección.

Hito: [Gestión Integral de Aplicación Parcial de Pagos y Anticipos (Fase 2)](https://binaural.odoo.com/odoo/action-1963/4820)

## Tarea 1 — Análisis técnico, diseño del Motor y configuración base

**Tarea:** https://binaural.odoo.com/odoo/action-341/78941
**Estado:** Cerrada
**Alcance:** únicamente el popover "Añadir" del widget de pagos pendientes
en factura (`invoice_outstanding_credits_debits_widget` /
`..._widget_advance_payment`). Registrar Pago, Conciliar Pagos y Asientos
Contables quedan para T2/T3.

### Qué se reusó de `solsica_partial_payment`

Módulo cliente de referencia: [`binaural-dev/solsica`](https://github.com/binaural-dev/solsica/tree/release/solsica_partial_payment).

- Patrón de enrutamiento por contexto en `js_assign_outstanding_line`
  (sin el monto en contexto, comportamiento idéntico a `l10n_ve_igtf` sin
  modificar).
- Patch JS sobre `AccountPaymentField` vía `patch()` (no reemplazo del
  componente), coexistiendo con el patch propio de `l10n_ve_igtf`.
- Estructura de test/documentación de referencia (no portada en este corte,
  ver "Pendiente").

**No reusado tal cual:** la dependencia a `account_payment_widget_amount`
(OCA) fue descartada por Solsica (D1 de su propio diseño) y no aplica aquí
tampoco. El popover de Solsica es de un solo input sin validaciones del lado
cliente; este módulo agrega validación de disponible, placeholder con el
monto sugerido, y aplicar-todo si se deja vacío.

### Arquitectura implementada

- `models/account_move.py`
  - `_is_advance_outstanding_line`: mismo predicado que
    `l10n_ve_igtf:672-674` (no se reimplementa el criterio).
  - `js_assign_outstanding_line`: lee `context["l10n_ve_partial_paid_amount"]`,
    valida (`>0`, `< residual`), y enruta a la rama de anticipo o a la rama
    estándar del core.
  - `can_apply_partial_payment`: accesor público para el JS, evita mostrar
    el popover si el usuario/compañía no tiene el permiso habilitado.
  - `prepare_advance_payment_vals`: neutraliza `force_balance` en parciales
    (ver "Limitación conocida" abajo).
- `models/account_move_line.py`
  - `_prepare_reconciliation_amls`: prorratea el candidato de conciliación
    **antes** de llamar a `super()` (no después), acotado a la línea de
    `context["move_id"]`/`context["line_id"]` para no afectar
    conciliaciones de diferencia cambiaria o base imponible en efectivo que
    corran bajo el mismo contexto ambiental.
- `static/src/js/account_payment_field_partial.js` +
  `static/src/xml/account_payment_templates.xml`: popover de monto único,
  con validación de disponible/inválido/negativo en cliente, y verificación
  de `can_apply_partial_payment` antes de abrir (si no aplica, se comporta
  como el "Añadir" original, sin popover).
- `models/res_company.py` + `models/res_config_settings.py` +
  `views/res_config_settings.xml`: flag `partial_pay_from_outstanding`
  (default `False`) en Binaural Settings → Pagos Parciales.
- `security/res_groups.xml`: grupo `group_partial_payment_apply`, otorgado
  por defecto a `account.group_account_manager` vía `implied_ids` (no
  reemplaza otros campos del grupo core). Controla tanto el uso del
  popover (servidor) como la visibilidad de la sección de configuración.
- Auditoría: `message_post` en el chatter de la factura con el monto
  realmente aplicado (calculado por diferencia de residual antes/después,
  no el solicitado), origen del pago, y saldo restante.
- `i18n/es_VE.po`: código fuente en inglés, traducción generada con el
  exportador nativo de Odoo (`odoo.tools.translate.trans_export`), no a
  mano.

### Limitación conocida (deuda, no bloqueante)

`force_balance` se neutraliza incondicionalmente (`None`) para cualquier
aplicación parcial de anticipo, en vez de recalcularse proporcionalmente.
Esto mantiene consistente una misma aplicación de anticipo
independientemente de cuántos parciales tomó, pero en escenarios
multimoneda (factura/anticipo en USD, compañía en VEF) la diferencia
cambiaria puede quedar distribuida distinto según si se aplicó en un solo
paso o en varios parciales. Documentado y aceptado como riesgo abierto para
refactor posterior (decisión del líder de tarea, no se investigó la
alternativa proporcional en este corte).

### Hallazgo relevante para el alcance general (sección 6.7)

En la rama de anticipos, `l10n_ve_igtf._create_advance_payment_move` genera
un asiento de cruce (`is_advance_move=True`) porque la cuenta de anticipo no
es la misma que CxC/CxP. Esto es una limitación real frente al requisito de
"sin asientos adicionales" del alcance general: no se puede evitar un
asiento de reclasificación cuando el anticipo vive en una cuenta separada.
La rama de créditos/pagos normales (no anticipo), en cambio, no genera
ningún asiento adicional — solo prorratea el `account.partial.reconcile`
estándar.

### Validado, no requiere cambio

- Notas de crédito: pasan por la rama no-anticipo del mismo widget sin
  tratamiento especial (no son "anticipo" según
  `_is_advance_outstanding_line`).
- "No aplicar documentos de otra compañía/partner incompatible": heredado
  del dominio propio del widget de pagos pendientes de Odoo, no
  reimplementado.

### Ajuste posterior a revisión funcional (Ari)

Una reviewer funcional del cliente pidió, en el chatter de la tarea, que el
popover "Añadir" mostrara además:

- Saldo restante del pago (calculado).
- Valor sugerido: el menor entre el saldo disponible del pago y el saldo
  pendiente de la factura.

Se implementó como un preview en vivo dentro del MISMO popover (sin agregar
una columna nueva a la tabla completa del widget de pagos pendientes — eso
excedería el alcance de esta tarea): el campo de monto se precarga con el
valor sugerido (editable/borrable, no de solo lectura), y una línea nueva
"Remaining payment balance" recalcula en vivo, con cada tecleo, exactamente
lo que aplicaría "Apply" en ese momento — incluyendo mostrar el mismo error
que se mostraría al aplicar (en vez de un número inventado) si el valor
actual del input sería rechazado. No se creó ningún flag/grupo nuevo: ambos
comportamientos viven siempre activos dentro del popover ya existente,
gateados por el flag `partial_pay_from_outstanding` + el grupo
`group_partial_payment_apply` ya existentes (ver `models/res_company.py`).

**Limitación de precisión (aceptada, no bloqueante):** el preview del saldo
restante es una estimación del lado del cliente (JS), exacta en el caso
simple —misma moneda entre factura y pago, sin IGTF de por medio— pero puede
diferir de lo que el servidor termine aplicando en anticipos de un diario
IGTF o en escenarios multimoneda, donde el servidor sí calcula el monto
exacto (ver `js_assign_outstanding_line` /
`l10n_ve_igtf._create_advance_payment_move`). Reproducir esa lógica fiscal
en JS para el preview se consideró fuera de alcance.

### Alerta de recorte de IGTF en anticipos (cambio de la decisión anterior)

Cuando se aplica un anticipo de un diario con IGTF y ese anticipo no tiene
saldo de sobra para cubrir también el IGTF, `l10n_ve_igtf` aplica
intencionalmente MENOS del monto pedido a la factura (ej. se piden $2,00 y
se aplican $1,94) — comportamiento correcto, confirmado con el consultor
contable del cliente, que este módulo NO modifica.

Lo que sí agrega este módulo es una alerta visual en el MISMO popover,
*antes* de aplicar: un nuevo método público de solo lectura,
`account.move.preview_advance_igtf_shortfall(line_id, paid_amount)`
(`models/account_move.py`), replica (sin persistir nada) la fórmula exacta de
`l10n_ve_igtf.account_move._create_advance_payment_move` /
`prepare_igtf_payment_vals` para estimar si el monto tecleado cae en ese
escenario, y de ser así, cuánto se aplicaría realmente. El JS (`static/src/js/account_payment_field_partial.js`) llama a este método vía RPC
con debounce (~300ms, `useDebounced` + `KeepLast`) en cada tecleo válido —
tanto para montos parciales como para el camino de aplicación "completa" del
mismo popover (monto igual o mayor al residual) — y muestra el mensaje de
alerta en el template cuando corresponde (`static/src/xml/account_payment_templates.xml`). El botón "Apply" nunca espera a este RPC.

Esto actualiza/reemplaza la limitación de precisión documentada arriba
**únicamente para este caso de recorte de IGTF**: el preview del saldo
restante sigue siendo una estimación 100% client-side (sin cambios), pero
ahora corre en paralelo una verificación server-side específica para avisar
de este recorte conocido. Un test de paridad
(`tests/test_advance_igtf_shortfall_preview.py`) aplica de verdad el pago y
compara el residual resultante contra lo que predijo el preview, para
blindar contra que la fórmula se desalinee con `l10n_ve_igtf` en el futuro.

**Nota sobre el `.po` de este ajuste:** los 3 strings nuevos (`Amount to
apply`, `Remaining payment balance:`, el mensaje de error de saldo pendiente
de factura) se agregaron a mano a `i18n/es_VE.po`, no vía
`trans_export` como el resto del archivo — la base de prueba disponible al
momento tenía datos desactualizados de módulos ajenos (`iap`, `ai_embedding`
sin la extensión `vector` de Postgres) que rompían cualquier `-u` de módulo,
incluso uno no relacionado a `l10n_ve_partial_payment`. Se agregaron
siguiendo exactamente el mismo formato/convención que ya usan las entradas
hermanas del mismo archivo, y se validó el resultado end-to-end en el
navegador (popover completo en español, incluido el mensaje de error nuevo).
Si se vuelve a regenerar el `.po` completo con `trans_export` más adelante,
confirmar que esos 3 msgid sobrevivan intactos.

### Pendiente (fuera de este corte, no de la tarea)

- Tests automatizados del Motor server-side: agregados (23 tests, 98% de
  cobertura — ver `tests/`). El ajuste fino de `force_balance` en sí
  (recálculo proporcional en vez de neutralizarlo, ver "Limitación conocida"
  arriba) sigue pendiente; los tests cubren el comportamiento actual
  (neutralizado), no la alternativa proporcional.
- Validación del cálculo del preview JS (saldo restante/sugerido, agregado
  en el ajuste posterior a revisión funcional de Ari, arriba): pendiente
  decidir entre tests JS (hoot) o checklist manual — todavía no se tomó esa
  decisión.
- Los otros 7 flags de configuración del alcance general (Registrar Pago,
  Conciliar Pagos, Asientos Contables, multi-factura, notas de crédito,
  mostrar saldo, editar sugerido) — se crean recién cuando exista el flujo
  que gobiernan, para no dejar flags sin comportamiento detrás.

## Tarea 2 — (pendiente)

_Flujo: wizard de Registrar Pago._

## Tarea 3 — (pendiente)

_Flujo: vista de Conciliar Pagos (distribución de un pago entre múltiples
facturas)._
