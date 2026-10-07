# l10n_ve_donation: `account_stock_journal_id` — RESUELTO (dependencia faltante, no campo faltante)

`models/stock_move.py` de `l10n_ve_donation` en v19, método
`_create_account_move()`:

```python
move_vals = {
    "journal_id": donation_moves.company_id.account_stock_journal_id.id,
    ...
}
```

Se había reportado inicialmente como "campo sin equivalente en v19" (por
error). **Corrección**: `res.company.account_stock_journal_id` es un
campo **CORE de Odoo** (`stock_account/models/res_company.py`, mismo
nombre, mismo tipo `Many2one("account.journal")`, mismo propósito) — no
es un campo propio de `l10n_ve_donation` ni de `binaural_advance_payment*`
que haya desaparecido. Confirmado NO es un rename hacia
`donation_account_id` (conceptos distintos: `account_stock_journal_id`
apunta a `account.journal`, `donation_account_id` a `account.account`,
para propósitos diferentes).

El problema original: `l10n_ve_donation/__manifest__.py` no declaraba
`"stock_account"` en `depends`, aunque el módulo lee directamente un
campo de `stock_account`. Cuando se escribió esta nota, sus dependencias
de entonces no lo traían y `_create_account_move()` fallaba con
`AttributeError` al primer scrap de donación. Hoy `stock_account` también
llega de forma transitiva (`l10n_ve_stock_account` → `sale_stock` →
`stock_account`), así que el fallo ya no se reproduce, pero el módulo no
debe depender de esa cadena para un campo que usa directamente.

**Corrección aplicada**: se declara `"stock_account"` en `depends` de
`l10n_ve_donation/__manifest__.py`. Se había agregado originalmente en
19.0.2.0.4 y se perdió en un merge con `19.0`; se reaplicó en 19.0.2.0.6.
No se crea ningún campo nuevo. La columna física
`res_company.account_stock_journal_id` no se toca (no hace falta migrarla
ni eliminarla: es la misma columna que Odoo core ya gestiona).

**Falso positivo descartado en el mismo repaso**:
`integra-addons/binaural_subsidiary_stock/models/stock_move.py:132`
tiene el mismo patrón de código, pero ese módulo **sí** declara
`"stock_account"` en su `__manifest__.py` -- nunca tuvo el problema.

La migración de datos real de este módulo (`donation_reason` → tags)
sigue en `pre-migrate.py`/`post-migrate.py` de esta misma carpeta, sin
cambios.
