# Tasks

## 1. Diagnóstico

- [x] 1.1 Reproducido el error: descargar el XLSX de una retención
      municipal con firma activa configurada devuelve un 500
- [x] 1.2 Identificado el traceback: `AttributeError: module 'odoo.tools'
      has no attribute 'image_process'` en `municipal_retention_xlsx.py`
- [x] 1.3 Confirmado en el core de Odoo (`odoo/tools/image.py`,
      `addons/base/models/ir_binary.py`) que `image_process` vive en
      `odoo.tools.image`, no en `odoo.tools`

## 2. Fix

- [x] 2.1 Import corregido a `from odoo.tools.image import image_process`
- [x] 2.2 Llamada actualizada a `image_process(...)`

## 3. Verificación

- [x] 3.1 Test de regresión con firma activa configurada (el caso del bug)
- [x] 3.2 Test de regresión sin firma configurada (caso sano, sin
      regresión)
- [x] 3.3 Confirmado que ambos tests fallan con el código anterior
      (`AttributeError`) y pasan con el fix, corridos en una base de datos
      limpia instalada desde cero
- [x] 3.4 Suite completa del módulo corrida en aislado: sin fallos

## 4. OpenSpec

- [x] 4.1 `proposal.md` + spec delta (`ADDED` - capability nueva)
- [ ] 4.2 `openspec validate --changes` (no ejecutado: CLI `openspec` no
      disponible en este entorno)

## 5. Proceso (pendiente, no técnico)

- [x] 5.1 Commit `[FIX] l10n_ve_payment_extension: firma no se inserta en
      Excel de retencion municipal` en la rama
      `maint-19.0-ti-15341-15076-15337-fix-retention-validations`
- [ ] 5.2 Push a `origin` (pendiente de confirmación explícita)
