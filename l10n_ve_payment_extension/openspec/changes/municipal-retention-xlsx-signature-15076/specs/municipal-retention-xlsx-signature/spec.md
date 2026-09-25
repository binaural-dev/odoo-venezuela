# Spec delta: municipal-retention-xlsx-signature

## ADDED Requirements

### Requirement: El reporte XLSX de retención municipal debe generarse correctamente cuando hay una firma activa configurada

El sistema SHALL generar y devolver el archivo XLSX de una retención
municipal (`municipal.retention.xlsx.xlsx_file()`) sin lanzar ninguna
excepción, tanto si existe un registro `signature.config` activo con
imagen de firma configurada, como si no existe ninguno.

#### Scenario: Descarga con firma activa configurada

- **GIVEN** una compañía con un `signature.config` activo que tiene una
  imagen de firma válida
- **WHEN** se solicita el reporte XLSX de una retención municipal
  (`/web/get_xlsx_municipal_retention`)
- **THEN** el archivo se genera y se devuelve como un XLSX válido, con la
  imagen de la firma insertada en el documento
- **AND** no se lanza ningún error interno del servidor

#### Scenario: Descarga sin firma configurada

- **GIVEN** una compañía sin ningún `signature.config` activo
- **WHEN** se solicita el reporte XLSX de una retención municipal
- **THEN** el archivo se genera y se devuelve como un XLSX válido, sin
  imagen de firma
- **AND** no se lanza ningún error interno del servidor
