# STATE

## Origen

Informe «Validación del módulo de donaciones: observaciones y hallazgos» (v3, Producto, 19 y
20/11/2026) y las dos tareas de mejora que salieron de él. Pedido de la tarea: llevar el módulo de
donaciones a Odoo 19 con la lógica de 17 y las donaciones recibidas, y corregir lo que encontró la
validación funcional. Las decisiones C1 a C6 son de Producto y Contabilidad y no son parte de este
change.

## Comandos

```bash
cd docker-odoo
# Actualizar el módulo en una base existente (corre la migración 19.0.3.0.1)
docker exec -u root <contenedor> odoo --stop-after-init -u l10n_ve_donation -d <base>
# Tests del módulo (incluye la cobertura: 97 % en la última corrida)
./odoo test <instancia> l10n_ve_donation --no-confirm
# Cobertura dirigida, si se necesita aparte
./scripts/coverage --odoo_container=<contenedor> --modules=odoo-venezuela/l10n_ve_donation --db_name=<base> --test_tags=/l10n_ve_donation
scripts/precommit <instancia> -m l10n_ve_donation
```

Instancia con `enterprise-19.0`, `odoo-venezuela`, `integra-addons` y `third-party-addons` 19.

## Resultado

**219 tests, 0 fallos, 0 errores** en toda la suite del módulo; pre-commit (`.po`, pylint
opcional y obligatorio) pasa.

Los ajustes de la validación funcional (REQ-DON-029 a 034) se prueban en archivos nuevos o
en los existentes: `test_donation_expense_accounts.py` (029), `test_donation_bank_statement.py`
(031), `test_donation_security_views.py` (034), `test_donation_credit_note_regression.py` (033,
con un control de la causa: el core toma la moneda de la nota de la lista de precios del
cliente), `test_received_donation.py` (030), `test_stock_move.py` (030),
`test_stock_picking.py` y `test_sale_account_move.py` (032).

| Archivo | Tests | REQ-ID |
|---|---|---|
| `test_received_donation.py` (clase de asientos) | 33 | 020, 021, 022, 023, 018, 027, 028 |
| `test_received_donation.py` (clase de recepción) | 21 | 024, 025, 018, 028 |
| `test_stock_picking.py` | 27 (incluye el del Recibo) | 019, 006 y los de la migración |
| `test_sale_account_move.py` | 37 (incluye `test_23b` a `test_23d`) | 026 y los de la migración |

Cada comportamiento se probó con un caso con control (la misma situación en la
dirección contraria o sin la condición): líneas con el donante en una recibida frente a
una otorgada, entrega con cuenta de recibidas frente a una correcta, recibo frente a
certificado. Los tests de cada corrección fallan sin ella.

## Límites conocidos

- El bloqueo del cambio de cuentas de recibidas se salta archivando la cuenta o cambiando su
  tipo: solo actúa en `res.company.write`. Se documenta como límite.
- Un borrador recibido al que se le quitan las cuentas se publica como otorgado con el donante
  en las líneas.
- Las recepciones ya hechas pierden su certificado si se quitan todas las cuentas de recibidas.
- El mensaje del bloqueo de cuentas lista cuentas que no están en uso.
- Dos textos de la recepción son imprecisos ("the only type that allows an account", "Cuenta de
  pérdida").
- REQ-DON-025 dice que el monto en bolívares "nunca falta", aunque sin tasa se omite el
  equivalente.
- El caso de borrador de `test_29` no se prueba y falta uno multicompañía.

- Quitar las cuentas de recibidas no se permite una vez publicada una recepción de donación:
  su asiento de valoración es una donación recibida.
- Quien valida un traslado valorado necesita el grupo «Costo Alterno (Ver)» si
  `binaural_foreign_cost` está instalado: la lectura vive en ese módulo, no en este.

- `ir.model.access.csv` da lectura, escritura, creación y borrado de `account.move` al grupo Gestor
  aunque no implique ningún grupo contable (ya era así antes de este cambio). La decisión (implicar
  `account.group_account_invoice` o dejarlo de solo lectura) es del líder técnico.
- El hook de la marca del extracto reevalúa cada cambio de líneas de los asientos de extracto
  (consulta las cuentas de donaciones recibidas de la compañía).

## Lo no verificado

- Los PDF no se renderizaron con wkhtmltopdf: los tests renderizan el HTML.
- Una compañía en USD con alterna en bolívares se probó a nivel del helper
  (`_compute_donation_amounts`) y con el cuerpo del certificado, no con un asiento real de otra
  compañía.
- La interfaz se recorrió en una base de pruebas; falta la validación funcional del consultor.
- La versión del manifest es `19.0.3.0.1`: la migración `migrations/19.0.3.0.1/post-migration.py`
  mueve el grupo Gestor a su privilegio propio y pasa el formato del Certificado a carta si sigue en
  A4, en las bases que ya tienen el módulo (el privilegio se probó en una copia de una base instalada;
  la migración completa, con tests de la función).
- El USD del documento como Bs ÷ tasa del día se fija con un test que simula un valor histórico en
  las líneas del asiento; la prueba con asientos de USD histórico reales (T04) la hace Producto en
  el staging.
- H1 y H10 no se recorrieron en el navegador: se comprobaron con tests y leyendo el widget del
  formulario de usuario de Odoo 19 (un grupo sin privilegio solo se dibuja en modo desarrollador, por
  eso el Gestor tiene privilegio propio).

## Próximos pasos

- [x] Ajustes de la validación funcional (REQ-DON-029 a 034) con sus tests.
- [x] Revisión del código con las reglas de Binaural; hallazgos corregidos (queda I3).
- [ ] Commits, push y revalidación de Producto en el staging con la versión `19.0.3.0.1`.
- [ ] Vincular el PR a la tarea 86967 y aprobar el código por el dueño técnico de la vertical.
- [ ] Producto: H8, H13, el RIF sin prefijo en otros módulos, el caso T04 y las mejoras C4 y C6.
- [ ] Líder técnico: permiso de `account.move` del grupo Gestor (I3).

