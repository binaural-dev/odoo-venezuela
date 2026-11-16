# STATE (2026-11-16)

Rama `19.0_feat-ta_86967_donation_received_documents`, 7 commits apilados sobre la rama
`19.0_feat-ta_86967_donation_module_1440_port` (4 de implementación, y uno de correcciones, uno de
traducción y uno de documentación). Sin push ni PR.

## Comando exacto

```bash
cd /home/rogerdev/binaural/docker-odoo
./odoo test donation-19.0 l10n_ve_donation
scripts/precommit donation-19.0 -m l10n_ve_donation
```

## Resultado

**185 tests, 0 fallos, 0 errores**; pre-commit (`.po`, pylint opcional y obligatorio) pasa.

| Archivo | Tests | REQ-ID |
|---|---|---|
| `test_received_donation.py` (clase de asientos) | 33 | 020, 021, 022, 023, 018, 027, 028 |
| `test_received_donation.py` (clase de recepción) | 21 | 024, 025, 018, 028 |
| `test_stock_picking.py` | 1 (+ el del recibo adaptado) | 019, 006 |
| `test_sale_account_move.py` | 3 en la rama 86967 (`test_23b` a `test_23d`) | 026 |

Cada comportamiento se probó con un caso con control (la misma situación en la
dirección contraria o sin la condición): líneas con el donante en una recibida frente a
una otorgada, entrega con cuenta de recibidas frente a una correcta, recibo frente a
certificado. Los tests de cada corrección fallan sin ella.

## Revisiones de código (revisor de Binaural, sin publicar)

Tres pasadas; los hallazgos se aplicaron en `320b652ea`, salvo los que se listan a
continuación, que **quedan abiertos por decisión** (tercera pasada):

- I1: el bloqueo de cuentas se salta archivando la cuenta o cambiando su tipo (solo actúa en
  `res.company.write`); alternativa: documentarlo como límite conocido.
- Menores: el borrador de `test_29` no prueba su caso y falta uno multicompañía; un borrador
  recibido al que se le quitan las cuentas se publica como otorgado con el donante en las
  líneas; las recepciones hechas pierden su certificado si se quitan todas las cuentas; el mensaje
  del bloqueo lista cuentas que no están en uso; dos textos de la recepción imprecisos
  ("the only type that allows an account", "Cuenta de pérdida"); REQ-DON-025 dice que el monto
  en bolívares "nunca falta" aunque sin tasa se omite el equivalente.

## Lo no verificado

- Los PDF no se renderizaron con wkhtmltopdf: los tests renderizan el HTML.
- Una compañía en USD con alterna en bolívares se probó a nivel del helper
  (`_compute_donation_amounts`) y con el cuerpo del certificado, no con un asiento real de otra
  compañía.
- La interfaz se recorrió con la base `donation_consultor` y su manual de pruebas, que el
  consultor debe ejecutar.
- M8: el manifest sigue en `19.0.3.0.0` (ya subió desde `19.0.2.0.6` en el commit de migración
  de la rama base).
