# Spec delta: pos-self-order-kiosk-required-fields-legend

## ADDED Requirements

### Requirement: Leyenda de campos obligatorios en los pasos de contacto

Los pasos de "completar teléfono" y "nuevo cliente" de `IdentificationPage` SHALL mostrar la leyenda "LOS CAMPOS MARCADOS CON * SON OBLIGATORIOS" encima
de los campos del formulario. El texto fuente SHALL ser traducible vía
`_t()`; el marcador "*" de cada campo individual (nombre, apellido, teléfono)
SHALL seguir agregándose fuera del término traducible base (p. ej.
`_t("Phone") + " *"`), sin alterar el msgid del término.

#### Scenario: Paso de completar teléfono

- **GIVEN** un cliente identificado por cédula sin teléfono registrado
- **WHEN** llega al paso de completar teléfono
- **THEN** ve la leyenda de campos obligatorios encima del campo teléfono

#### Scenario: Paso de nuevo cliente

- **GIVEN** una cédula no encontrada
- **WHEN** el cliente llega al paso de creación de contacto
- **THEN** ve la leyenda de campos obligatorios encima de los campos del
  formulario (nombre, apellido, teléfono)
