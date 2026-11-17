# STATE

## Comandos

```bash
cd docker-odoo
./odoo test <instancia> l10n_ve_donation
scripts/precommit <instancia> -m l10n_ve_donation
```

Instancia con `enterprise-19.0`, `odoo-venezuela`, `integra-addons` y `third-party-addons` 19.

## Resultado

**185 tests, 0 fallos, 0 errores** en toda la suite del módulo; pre-commit (`.po`, pylint
opcional y obligatorio) pasa.

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

## Lo no verificado

- Los PDF no se renderizaron con wkhtmltopdf: los tests renderizan el HTML.
- Una compañía en USD con alterna en bolívares se probó a nivel del helper
  (`_compute_donation_amounts`) y con el cuerpo del certificado, no con un asiento real de otra
  compañía.
- La interfaz se recorrió en una base de pruebas; falta la validación funcional del consultor.
- La versión del manifest es `19.0.3.0.0`.
