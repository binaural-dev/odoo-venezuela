# pos-odoo19-frontend Specification

## Purpose

Reunir las reglas que gobiernan el frontend del PdV de `l10n_ve_pos` en Odoo
19: cómo se escriben y mantienen los overrides OWL bajo `static/src`, que se
empaquetan en el bundle `point_of_sale._assets_pos` mediante globs declarados
en `__manifest__.py`.

Las convenciones técnicas de la migración V17 → V19 (renombrados de API,
trampas conocidas, prohibición de `Math.*` en favor de los métodos nativos de
moneda) viven en `openspec/migration-lessons.md`; esta capability recoge las
que se han formalizado como requirement.
## Requirements
### Requirement: Los overrides descartados se eliminan, no se dejan comentados en el bundle

El módulo SHALL NO contener bajo `static/src` ficheros cuyo contenido sea
íntegramente comentario o esté vacío. Una personalización del frontend que
se descarta —porque la API de Odoo que parcheaba desapareció, porque su
lógica se reimplementó en otro sitio, o porque ya no se quiere— SHALL
eliminarse del repositorio; su historia queda en git.

La razón es que los assets del PdV se declaran con globs
(`__manifest__.py`: `"l10n_ve_pos/static/src/**/**"`), así que todo
fichero bajo `static/src` entra en el bundle `point_of_sale._assets_pos`
sin declaración explícita. Un fichero íntegramente comentado no ejecuta
nada, pero sí aparece en toda búsqueda de código como si fuera vigente y
obliga a descartarlo a mano en cada migración o depuración.

#### Scenario: Se descarta una personalización durante una migración

- **GIVEN** un override del frontend del PdV cuya API nativa ya no existe
  en la versión destino
- **WHEN** se decide no portarlo
- **THEN** el fichero se elimina del repositorio, y no se deja como
  fichero comentado bajo `static/src`

#### Scenario: La lógica de un override se reimplementa en otro fichero

- **GIVEN** una característica cuyo override original se sustituyó por
  otra implementación viva en un fichero distinto (p. ej. el filtro de
  productos sin stock, que pasó de `product_list.js` a
  `product_screen.js`)
- **WHEN** la nueva implementación queda operativa
- **THEN** el fichero antiguo se elimina, de modo que no existan dos
  fuentes aparentes de la misma característica

#### Scenario: Auditoría del contenido de `static/src`

- **GIVEN** el módulo con sus assets declarados por globs
- **WHEN** se cuentan las líneas activas (no comentario, no vacías) de
  cada fichero bajo `static/src`
- **THEN** ningún fichero empaquetado tiene cero líneas activas, ni es un
  fichero de 0 bytes

### Requirement: Los montos de una línea de pago se muestran completos

El PdV SHALL mostrar completos los montos de una línea de pago (el de la moneda
del método y, si lo hay, el de la otra moneda): MUST NOT truncarlos. Si no caben
junto al nombre del método, SHALL pasarlos a una segunda fila; lo que puede
truncarse es el nombre.

#### Scenario: Método foráneo en la caja VES

- **GIVEN** la caja VES con la tasa a 803,34
- **WHEN** el cajero cobra 70 $ con Efectivo USD (Caja VES)
- **THEN** la línea muestra "$ 70,00 / 56.233,80 Bs.F" completo, no "$ 70,00 / 56.2…"

#### Scenario: Par de montos que no cabe en una fila

- **GIVEN** una línea de pago con montos tan largos que el par no cabe en el ancho de la columna
- **WHEN** se muestra la pantalla de pago
- **THEN** el par se parte por el " / " y los dos montos se ven completos

#### Scenario: Línea que cabe en una fila

- **GIVEN** una línea de pago cuyo nombre y montos caben en el ancho de la columna
- **WHEN** se muestra la pantalla de pago
- **THEN** la línea sigue en una sola fila

