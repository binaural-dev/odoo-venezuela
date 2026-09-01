# l10n_ve_donation: defecto de código en v19, no cubierto por esta migración

`models/stock_move.py` de `l10n_ve_donation` en v19, método
`_create_account_move()`, línea ~35:

```python
move_vals = {
    "journal_id": donation_moves.company_id.account_stock_journal_id.id,
    ...
}
```

`res.company.account_stock_journal_id` **no existe en v19** (el módulo
solo declara `donation_account_id` ahora). Esta línea va a fallar la
primera vez que se procese un scrap de donación en producción
(`AttributeError`/campo inexistente).

Esto es un bug del código de `l10n_ve_donation` v19, no algo que un script
de migración de datos pueda arreglar — no hay ninguna transformación de
datos que corrija código que referencia un campo que ya no existe.

Opciones para resolverlo (a decidir por el equipo de desarrollo):
- Agregar de vuelta `account_stock_journal_id` a `res.company` en v19, o
- Cambiar esa línea para derivar el diario desde `donation_account_id`
  (ej. el diario por defecto asociado a esa cuenta) o desde otra
  configuración ya existente en v19.

Repórtalo como incidencia de código antes de dar por cerrada la
migración de este módulo — la migración de datos (`donation_reason` →
tags, backup de `account_stock_journal_id`) ya está resuelta en
`pre-migrate.py`/`post-migrate.py` de esta misma carpeta.
