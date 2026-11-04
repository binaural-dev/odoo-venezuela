# Tasks

## 1. Implementación

- [x] 1.1 Método `action_download_retention_voucher` en `account.move`
- [x] 1.2 Método `action_print_retention_voucher_pdf` y botón en el formulario
      de las retenciones IVA, ISLR y municipal, visible solo si está emitida
- [x] 1.3 Tres botones en la cabecera del documento, visibles según el tipo de
      retención emitida

## 2. Traducción

- [x] 2.1 Traducciones en `i18n/es_VE.po`

## 3. Verificación

- [x] 3.1 Probado en la base `yahir2a`: la acción devuelve el reporte para
      IVA, ISLR y municipal, falla con un mensaje claro si no hay retención
      emitida, y los tres botones aparecen en la vista
- [ ] 3.2 Pruebas automáticas: no incluidas en este cambio
- [ ] 3.3 Corrida del CI del PR

## 4. OpenSpec

- [x] 4.1 `proposal.md` + spec delta (`ADDED`: capability nueva)
- [ ] 4.2 `openspec validate --changes` (no ejecutado: CLI `openspec` no
      disponible en este entorno)
