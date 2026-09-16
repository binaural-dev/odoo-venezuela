# Spec delta: pos-odoo19-frontend

## ADDED Requirements

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
