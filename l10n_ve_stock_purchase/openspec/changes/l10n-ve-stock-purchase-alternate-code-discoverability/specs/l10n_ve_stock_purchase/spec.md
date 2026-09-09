## ADDED Requirements

### Requirement: Descubribilidad del Código Alterno en la metadata del módulo
El summary y la description del manifest del módulo, así como su entrada en el `README.md` raíz del repositorio, DEBEN (MUST) mencionar explícitamente que el módulo resuelve búsqueda y visualización de Código Alterno en la línea de compra, de forma que la capacidad sea encontrable desde el listado de Apps o el README sin necesidad de leer el código.

#### Scenario: Búsqueda en Apps por código alterno
- **WHEN** un usuario busca "código alterno" en Settings > Apps
- **THEN** `l10n_ve_stock_purchase` aparece en los resultados, por coincidir con su summary/description

#### Scenario: Lectura del README raíz
- **WHEN** alguien lee la tabla de módulos del `README.md` del repositorio buscando dónde se resuelve el código alterno en compras
- **THEN** la entrada de `l10n_ve_stock_purchase` lo menciona explícitamente
