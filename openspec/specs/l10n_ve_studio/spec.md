# l10n_ve_studio

## Purpose

Restringe el uso de Odoo Studio en las instalaciones de la localización venezolana: impide instalar `web_studio` y lo desinstala si ya estaba presente. Extiende `ir.module.module`. Depende de `l10n_ve_base`.

## Requirements

### Requirement: Bloqueo de instalación de módulos restringidos

El sistema DEBE (MUST) impedir la instalación de los módulos listados en `RESTRICTED_MODULES` (actualmente `web_studio`), lanzando un error al intentar instalarlos vía `button_immediate_install`.

#### Scenario: Intento de instalar Studio

- **WHEN** un administrador intenta instalar el módulo `web_studio` desde la lista de aplicaciones
- **THEN** se lanza un error indicando que la instalación del módulo está bloqueada y la instalación no procede

### Requirement: Desinstalación de Studio al instalar este módulo

Al instalarse este módulo, el hook `post_init_hook` DEBE (MUST) desinstalar `web_studio` si se encuentra en estado `installed`.

#### Scenario: Studio previamente instalado

- **WHEN** se instala `l10n_ve_studio` en una base de datos donde `web_studio` está instalado
- **THEN** `web_studio` queda desinstalado al finalizar la instalación
