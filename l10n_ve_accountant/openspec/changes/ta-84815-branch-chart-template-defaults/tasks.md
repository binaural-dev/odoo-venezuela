# Tareas

- [x] 1. `_post_load_data` en `models/account_chart_template.py` con respaldo solo para sucursales.
- [x] 2. Respaldo con default global (no copia ni falla) y exclusión de propiedades de `res.company` (revisión de código).
- [x] 3. Tests `test_branch_chart_template_defaults.py` (6 unitarios + 1 de extremo a extremo), registrados en `tests/__init__.py`.
- [x] 4. Bump de versión `19.0.1.1.7` → `19.0.1.1.8`.
- [x] 5. Verificar que los tests fallan sin el cambio y pasan con él.
- [x] 6. Suite completa de `l10n_ve_accountant`: sin regresiones (los 5 fallos de `TestProductTemplate` ya existen en `origin/19.0`, ver `STATE.md`).
- [x] 7. Requirement agregado a `openspec/specs/l10n_ve_accountant/spec.md` (estado actual).
- [x] 8. Revisión de SaulOrte: `UserError` solo para por cobrar y por pagar (resto `warning`), mensaje único con todas las faltantes, test de matriz sin `chart_template`.
