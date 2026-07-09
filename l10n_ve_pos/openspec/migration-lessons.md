# Migration Lessons: l10n_ve_pos Odoo 17 → 19

## API renames (canonical mapping)

| v17 | O19 | Dónde aplica |
|-----|-----|-------------|
| `Order` | `PosOrder` | `@point_of_sale/app/models/pos_order` |
| `Payment` | `PosPayment` | `@point_of_sale/app/models/pos_payment` |
| `usePos` | `usePos` (same name) | `@point_of_sale/app/hooks/pos_hook` (not `app/store/pos_hook`) |
| `get_paymentlines()` | `payment_ids` (getter) | `Array.from(this.payment_ids \|\| [])` |
| `get_total_with_tax()` | `totalDue` (getter) | `Number(this.totalDue ?? 0) \|\| 0` |
| `get_due()` | `remainingDue` (getter) | `Number(this.remainingDue ?? 0) \|\| 0` |
| `add_paymentline(method)` | `addPaymentline(method)` | camelCase rename |
| `select_paymentline(line)` | `selectPaymentline(line)` | camelCase rename |
| `assert_editable()` | `assertEditable()` | camelCase rename |
| `electronic_payment_in_progress()` | `electronicPaymentInProgress()` | camelCase rename |
| `selected_paymentline` | `selectedPaymentLine` | camelCase rename |
| `payment.cid` | `payment.uuid` | property rename |
| `payment.payment_method` | `payment.payment_method_id` | `payment_method` is `undefined` → always use `payment_method_id` with `?.` |
| `new Payment(env, opts)` | `this.models["pos.payment"].create({pos_order_id: this, ...})` | O19 registry pattern |
| `this.paymentlines.add(line)` | auto via `pos_order_id` in create | no manual add needed |
| `formatCurrency(amt, 'Product Price')` | `formatCurrency(amt)` | O19 accepts only value, no format type |
| `Payment.prototype` | `PosPayment.prototype` | import + patch target |
| `Order.prototype` | `PosOrder.prototype` | import + patch target |

## CRITICAL: NO usar `this.pos` en PosOrder

**En Odoo 17**, `this.pos` estaba disponible en el `setup()` del PosOrder. **En Odoo 19, NO.** El core no asigna `this.pos` al PosOrder.

**En Odoo 19**, el PosOrder obtiene el contexto a través de getters nativos:

```js
// En lugar de this.pos.currency.rounding:
this.currency.rounding      // → this.config.currency_id.rounding

// En lugar de this.pos.config.XXXX:
this.config.XXXX             // → this.models["pos.config"].getFirst().XXXX

// En lugar de this.pos.currency.rounding en compute_igtf_amount:
this.currency.rounding
this.config.igtf_percentage
```

**`this.currency`** es un getter del core PosOrder que retorna `this.config.currency_id`.

**`this.config`** es un getter del core PosOrder que retorna `this.models["pos.config"].getFirst()`.

Ambos están disponibles en `setup()` porque el core los setea vía `this.config_id = this.config` o desde `vals.json`.

**Excepción**: en `PaymentScreen` y `PaymentScreenStatus` (componentes OWL), `this.pos` se obtiene vía `usePos()` hook. Ahí SÍ está disponible.

## Silent-trap: `?.() || 0`

El patrón `x?.method?.() || 0` es peligroso en migraciones donde métodos se convirtieron en getters:
- Si `method` fue renombrado a getter, `x.method` es `undefined`
- `undefined?.()` retorna `undefined`
- `undefined || 0` retorna `0`
- **El código nunca falla, solo devuelve 0**

**Patrón defensivo recomendado**:
```js
const value = Number(
  this.totalDue ??
  (typeof this.get_total_with_tax === "function" ? this.get_total_with_tax() : 0)
) || 0;
```

## `update_igtf()` timing

En O17, `update_igtf()` se llamaba en `setup()` y `this.pos` ya existía. En O19, si se usa `this.currency`/`this.config` en vez de `this.pos`, se puede seguir llamando en `setup()` sin problemas.

## OWL QWeb templates

- Los templates OWL con `t-inherit-mode="extension"` y `owl="1"` se cargan como parte del asset bundle JS, NO como vistas en `ir.ui.view`
- Las XPath expressions se evalúan contra el template BASE (el del core), que se compila y cachea en el JS
- `hasclass('classname')` es la forma correcta de filtrar por clase
- Para verificar que un XPath funciona, hay que leer el template nativo O19 dentro del contenedor Docker

## Bundle caching

Cuando se modifican archivos JS o XML de OWL templates:
1. El módulo debe actualizarse (`-u modulo` o UI Upgrade)
2. Los assets se regeneran con nuevo hash
3. Si el hash no cambia, es porque Odoo no encontró cambios en los archivos
4. Verificar que el archivo modificado está en el directorio correcto que el contenedor está montando
