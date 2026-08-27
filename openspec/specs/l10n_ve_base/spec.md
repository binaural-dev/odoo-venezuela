# l10n_ve_base

## Purpose

Módulo base técnico de la localización venezolana. No implementa lógica de negocio: provee los puntos de anclaje que el resto de la localización extiende — la app "Binaural Settings" en los ajustes generales, la marca `binaural` en los módulos, y ajustes de seguridad/depuración del entorno. Depende solo de `base` y `web`; prácticamente todos los módulos `l10n_ve_*` dependen de él directa o indirectamente.

## Requirements

### Requirement: Marca de módulos Binaural

El modelo `ir.module.module` DEBE (MUST) exponer el campo booleano `binaural` con valor por defecto `False`, para poder distinguir los módulos de Binaural del resto de los módulos instalados.

#### Scenario: Módulo sin marcar

- **WHEN** se consulta un módulo cualquiera que no ha sido marcado
- **THEN** su campo `binaural` es `False`

### Requirement: App de ajustes "Binaural Settings"

La vista de ajustes generales (`res.config.settings`) DEBE (MUST) incluir una app llamada "Binaural Settings" con `name="l10n_ve_base"`, que contiene el bloque `l10n_ve_base_block`. Esta app es el punto de anclaje donde los demás módulos de la localización (por ejemplo `l10n_ve_rate`) insertan sus propios bloques de configuración vía herencia de vista.

#### Scenario: App visible en ajustes

- **WHEN** un usuario administrador abre Ajustes generales con el módulo instalado
- **THEN** aparece la sección "Binaural Settings" en el panel de configuración

### Requirement: Eliminación de "Become Superuser" del menú de depuración

El cliente web DEBE (MUST) eliminar la opción "Become Superuser" del menú de depuración (registro `debug.default`), impidiendo el acceso a esa acción incluso con el modo desarrollador activo.

#### Scenario: Menú debug sin superusuario

- **WHEN** un usuario con modo desarrollador activo abre el menú de depuración
- **THEN** la opción "Become Superuser" no está disponible

### Requirement: Acceso de administración sobre vistas

El grupo `base.group_system` DEBE (MUST) tener permisos completos (leer, escribir, crear, eliminar) sobre `ir.ui.view` vía la ACL `base.access_ir_ui_view_group_system`.

#### Scenario: Administrador edita una vista

- **WHEN** un usuario del grupo `base.group_system` crea o modifica un registro de `ir.ui.view`
- **THEN** la operación es permitida por la ACL del módulo
