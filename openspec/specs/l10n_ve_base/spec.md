# l10n_ve_base

## Purpose

Módulo base técnico de la localización venezolana. No implementa lógica de negocio: provee los puntos de anclaje que el resto de la localización extiende — la app "Binaural Settings" en los ajustes generales, la marca `binaural` en los módulos, la etiqueta de migración de cada módulo en Aplicaciones, y ajustes de seguridad/depuración del entorno. Depende solo de `base` y `web`; prácticamente todos los módulos `l10n_ve_*` dependen de él directa o indirectamente.

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

### Requirement: Etiqueta de migración de los módulos en Aplicaciones

El modelo `ir.module.module` DEBE (MUST) exponer el campo `migration_state`, calculado y no almacenado, con tres valores posibles:

- **Migrado** (`migrated`): el manifiesto del módulo trae la clave `binaural_migrated` en verdadero, es decir el módulo ya está migrado a esta versión de Odoo;
- **Pendiente de migrar** (`pending`): el módulo no es de Odoo, no trae la clave y no se puede instalar en esta versión (estado `uninstallable`);
- vacío: cualquier otro módulo. Los módulos de Odoo (autor que empieza por «Odoo S», community y enterprise) nunca llevan etiqueta.

El manifiesto se lee cuando la pantalla lo pide, no al actualizar la lista de aplicaciones: marcar un módulo como migrado se ve sin actualizar nada. En Aplicaciones, la tarjeta y la lista DEBEN (MUST) mostrar la insignia solo cuando el módulo está pendiente de migrar (en la lista, como columna opcional visible), y la búsqueda DEBE (MUST) ofrecer los filtros «Migrado» y «Pendiente de migrar». Buscar por el campo DEBE (MUST) dar lo mismo que el cálculo, también para los módulos sin etiqueta, y solo lee los manifiestos de los módulos que no son de Odoo.

#### Scenario: Módulo migrado

- **WHEN** el manifiesto de un módulo de Binaural trae `"binaural_migrated": True`
- **THEN** el módulo aparece con el filtro «Migrado»

#### Scenario: Módulo pendiente de migrar

- **WHEN** un módulo que no es de Odoo sigue con `"installable": False` y sin la clave
- **THEN** su tarjeta en Aplicaciones muestra la insignia «Pendiente de migrar» y aparece con el filtro del mismo nombre

#### Scenario: Módulo de Odoo que no se puede instalar

- **WHEN** un módulo de Odoo no se puede instalar en esta versión
- **THEN** no lleva etiqueta, no aparece con ninguno de los dos filtros y sí aparece al buscar los módulos sin etiqueta

### Requirement: Actualizar módulos no rompe la ciudad de los contactos

Mientras una base de 20 conserva las ciudades viejas de la localización (la tabla `res_country_city`, que `l10n_ve_location` borra al actualizarse a 20.0.1.0.1, ver su spec), actualizar `l10n_ve_base` o cualquier módulo que cargue entre `base_address_extended` y `l10n_ve_location` y toque `res.partner` (`mail`, `contacts`…) NO DEBE (MUST NOT) fallar por la ciudad de los contactos: la clave foránea de `res_partner.city_id` DEBE (MUST) quedarse apuntando a las ciudades viejas hasta que `l10n_ve_location` mueva las ciudades. En una base donde la clave ya apunta a `res.city`, o sin la tabla vieja, el módulo no hace nada.

Esto es un paliativo de la migración (R-49): Odoo 20 instala `base_address_extended` con `account`, y ese módulo define `city_id` hacia `res.city`; sin el paliativo, el registro a medio cargar pide la clave hacia `res_city` y la actualización se detiene con un error de clave foránea. Se puede quitar cuando ninguna base conserve la tabla `res_country_city`.

#### Scenario: Actualizar antes de mover las ciudades

- **WHEN** se actualiza `l10n_ve_base` (o `mail`) en una base de 20 cuyos contactos tienen ciudades de `res_country_city`
- **THEN** la actualización termina sin errores, los contactos conservan su ciudad y la clave de `city_id` sigue apuntando a `res_country_city`

#### Scenario: Base con las ciudades ya movidas

- **WHEN** se actualiza `l10n_ve_base` en una base donde la clave de `city_id` ya apunta a `res_city`
- **THEN** Odoo maneja la clave como siempre y el módulo no la toca
