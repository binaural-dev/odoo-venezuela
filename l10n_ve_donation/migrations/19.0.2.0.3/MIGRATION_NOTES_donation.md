# l10n_ve_donation: defecto de código en v19, no cubierto por esta migración

`models/stock_move.py` de `l10n_ve_donation` en v19, método
`_create_account_move()`, línea ~35:

```python
move_vals = {
    "journal_id": donation_moves.company_id.account_stock_journal_id.id,
    ...
}
```

`res.company.account_stock_journal_id` **no existe en v19 como campo
declarado en ningún módulo** -- verificado que NO es un rename hacia
`donation_account_id` (conceptos distintos: `account_stock_journal_id`
apunta a `account.journal`, `donation_account_id` a `account.account`,
para propósitos diferentes). Esta línea va a fallar la primera vez que
se procese un scrap de donación en producción (`AttributeError`).

**Segundo módulo con el mismo bug, encontrado en auditoría posterior**:
`integra-addons/binaural_subsidiary_stock/models/stock_move.py:132`
tiene exactamente el mismo patrón (`self.company_id.account_stock_journal_id.id`),
también sin que su propio `res_company.py` (o ningún otro módulo v19)
declare el campo. Mismo bug, mismo síntoma, módulo distinto.

Esto es un bug del código de AMBOS módulos v19, no algo que un script
de migración de datos pueda arreglar — no hay ninguna transformación de
datos que corrija código que referencia un campo que ya no existe.
**Por esto mismo, la migración de datos NO elimina la columna**
`res_company.account_stock_journal_id` (a diferencia del resto de
columnas huérfanas de este proyecto, que sí se respaldan y eliminan):
borrarla perdería el dato de configuración del cliente antes de que el
código se corrija. Se deja la columna intacta en `res_company` (con
respaldo adicional en la tabla de backup, redundante pero inofensivo).

Opciones para resolverlo (a decidir por el equipo de desarrollo, en
AMBOS módulos):
- Agregar de vuelta `account_stock_journal_id` a `res.company` en v19
  (en el módulo que corresponda), o
- Cambiar esas líneas para derivar el diario desde `donation_account_id`
  (ej. el diario por defecto asociado a esa cuenta) o desde otra
  configuración ya existente en v19.

Repórtalo como incidencia de código antes de dar por cerrada la
migración de este módulo — la migración de datos (`donation_reason` →
tags) ya está resuelta en `pre-migrate.py`/`post-migrate.py` de esta
misma carpeta; `account_stock_journal_id` queda deliberadamente sin
tocar, no como pendiente.
