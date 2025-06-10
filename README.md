# Localización Venezolana para Odoo

## Propósito de esta Localización

En Binaural C.A., estamos comprometidos con el desarrollo de herramientas que impulsen la mejora continua de nuestro país. Por eso, hemos decidido liberar esta localización venezolana para Odoo con el objetivo de:

- Construir una localización **robusta**, **estable** y **escalable** que cumpla con las necesidades fiscales, contables y legales de Venezuela.
- Permitir que la comunidad de software libre pueda colaborar y aportar ideas que optimicen las herramientas existentes y fomenten el crecimiento tecnológico en el país.
- Promover la colaboración y la mejora colectiva a través del trabajo conjunto de empresas, desarrolladores y usuarios.

## ¿Cómo Realizar Aportes?

Si deseas contribuir a esta localización, a continuación te explicamos cómo puedes hacerlo:

### 1. Reportar Bugs

Si encuentras un error o problema en los módulos, puedes:

- Crear un _issue_ en este repositorio, proporcionando:
  - Una descripción detallada del problema.
  - Los pasos para reproducir el error.
  - Capturas de pantalla o registros (si aplica).

### 2. Sugerir Mejoras o Nuevas Funcionalidades

Si tienes ideas para mejorar la localización o deseas proponer nuevas funcionalidades:

- Abre un _issue_ con el tipo "Mejora".
- Describe:
  - Qué problema o necesidad estás intentando resolver.
  - Tu propuesta para solucionarlo.
  - Cualquier referencia o material adicional que pueda ser útil.

### 3. Contribuir con Código

Si deseas colaborar directamente con código:

1. Haz un _fork_ de este repositorio.
2. Realiza los cambios en una rama nueva basada en `main` (por ejemplo, `feature/nueva-funcionalidad` o `fix/bug-en-reportes`).
3. Envía un _pull request_ (PR) con una descripción clara de:
   - Qué problema soluciona o qué funcionalidad añade tu contribución.
   - Cómo se puede probar tu cambio.
4. Asegúrate de cumplir con las siguientes pautas:
   - Todo nuevo desarrollo debe incluir pruebas automatizadas (si aplica).
   - El código debe seguir las guías de estilo de Odoo.

## Resumen de Módulos Incluidos

Esta localización incluye los siguientes módulos, diseñados para cumplir con los requisitos específicos de la normativa venezolana:

- **l10n_ve_accounting**  
   Gestión contable adaptada a los estándares locales. Incluye configuraciones específicas para cuentas y planes contables venezolanos, permitiendo cumplir con los requerimientos fiscales nacionales.

- **l10n_ve_tax**  
   Manejo de impuestos nacionales como IVA, retenciones y contribuyentes especiales. Asegura que los cálculos y reportes sean conformes con las leyes fiscales de Venezuela.

- **l10n_ve_rate**  
   Gestión de tasas de cambio oficiales. Actualización automática de las tasas de cambio, con la posibilidad de configurarlas por compañía y la opción de un fallback a la última tasa registrada en caso de no haber actualización oficial.

- **l10n_ve_invoice**  
   Emisión de facturas adaptadas a los requisitos legales. Incluye compatibilidad con reportes fiscales necesarios para cumplir con la normativa de facturación en Venezuela.

- **l10n_ve_location**  
   Incorporación de estados, municipios y parroquias de Venezuela en el módulo de contactos. Permite una gestión geográfica más precisa de los datos de socios y clientes dentro de Odoo.

- **l10n_ve_currency_rate_live**  
   Actualización diaria automática de tasas BCV. Configuración por compañía, con un sistema de fallback en caso de que no se reciba la actualización oficial.

- **l10n_ve_igtf**  
   Implementa la gestión automatizada del Impuesto a las Grandes Transacciones Financieras (IGTF). Gestiona los porcentajes y las cuentas asociadas al impuesto, con cálculos automáticos en las facturas y pagos. La integración es total con el módulo contable, lo que garantiza que todos los movimientos relacionados con el IGTF sean contabilizados correctamente.

- **l10n_ve_iot_mf**  
   Conexión segura vía IoT Box con protocolos fiscales y SDK HKA integrado. Permite la trazabilidad completa en las facturas, incluyendo el número de serie del dispositivo, la numeración fiscal única y el reporte Z.

- **l10n_ve_payment_extension**  
   Modelos especializados para retenciones, con cabeceras, líneas detalladas y tipos configurables (ISLR, municipales, etc.). Incluye campos dedicados en facturas y pagos para vincular retenciones y montos en divisa, con validación automática de cálculos según parámetros legales.

- **l10n_ve_pos**  
   Integración con el sistema de Punto de Venta (POS). Soporta tasas BCV actualizadas automáticamente para cálculos en BsD, USD o EUR, con límites configurables de diferencial cambiario según regulaciones locales. Además, permite la validación de tasas durante la apertura y cierre de sesiones.

- **l10n_ve_pos_igtf**  
   Implementación del IGTF en las operaciones de pago dentro del Punto de Venta. Permite habilitar o deshabilitar la aplicación del IGTF por método de pago, con validación de montos acumulados por sesión.

- **l10n_ve_pos_mf**  
   Integración con máquinas fiscales en el sistema de Punto de Venta para Venezuela. Permite registrar transacciones fiscales y generar reportes Z, garantizando que las ventas cumplan con la normativa fiscal del país.

- **l10n_ve_purchase**  
   Gestión de compras adaptada a las normativas fiscales venezolanas. Incluye la gestión de proveedores y la emisión de documentos de compra conforme a los requerimientos del SENIAT.

- **l10n_ve_ref_bank**  
   Referencias bancarias para transacciones fiscales. Este módulo facilita la integración de las transacciones bancarias con el sistema contable y fiscal de Odoo.

- **l10n_ve_sale**  
   Gestión de ventas adaptada a las regulaciones fiscales venezolanas. Incluye la emisión de facturas y la generación de reportes fiscales necesarios para cumplir con la legislación tributaria.

- **l10n_ve_stock**  
   Gestión de inventarios adaptada a las normativas venezolanas. Controla el movimiento de inventarios y proporciona reportes de stock en tiempo real, alineados con los requisitos fiscales locales.

- **l10n_ve_stock_account**  
   Gestión de contabilidad de inventarios adaptada a las normativas fiscales venezolanas. Permite realizar el seguimiento y la contabilidad de los movimientos de inventarios de acuerdo con los requerimientos del SENIAT.

- **l10n_ve_stock_purchase**  
   Gestión de compras de inventarios con integración fiscal. Este módulo permite la creación de órdenes de compra y la integración de los movimientos de inventario con el sistema contable y fiscal.

- **l10n_ve_stock_reports**  
   Informes relacionados con la gestión de inventarios y operaciones fiscales. Este módulo genera reportes detallados que ayudan a las empresas a cumplir con las regulaciones fiscales en términos de inventarios.

- **l10n_ve_studio**  
   Extensión del módulo Studio para personalización de campos y vistas. Permite crear y adaptar rápidamente campos, formularios y vistas para ajustarse a las necesidades de cada negocio.

- **l10n_ve_tax**  
   Gestión de impuestos, retenciones y tributos locales en Odoo. Permite la configuración de impuestos locales, como el IVA, y facilita la generación de reportes fiscales conforme a la ley venezolana.

- **l10n_ve_tax_payer**  
   Registro y control de contribuyentes fiscales en Venezuela. Gestiona los datos de los contribuyentes y facilita el seguimiento de sus obligaciones fiscales.

## Módulos de terceros requeridos/recomendados:

  - **Security Master (Recomendado)**  
    Función principal: Gestiona los reportes de auditoría exigidos por el SENIAT para cambios en modelos del sistema.  
    [Descargar en Odoo Store](https://apps.odoo.com/apps/modules/16.0/tk_security_master)

  - **Journal Sequence (Requerido)**  
    Función principal: Administra las secuencias numéricas de diarios contables (facturas y notas de crédito).  
    Importancia: Dependencia esencial para el funcionamiento del módulo l10n_ve_accountant.  
    [Descargar en Odoo Store](https://apps.odoo.com/apps/modules/16.0/od_journal_sequence)

## TODO: Planteamientos Futuros

Estamos trabajando para mejorar continuamente esta localización. Entre nuestros próximos pasos están:

1. **Runbot para pruebas en tiempo real**
   - Configurar un _runbot_ accesible para que los usuarios puedan:
     - Probar las funcionalidades actuales.
     - Validar los desarrollos más recientes.
     - Detectar errores antes de integrarlos en producción.

2. **Expansión de funcionalidades**
   - Incorporación de reportes más detallados.
   - Automatización de procesos administrativos y fiscales.

3. **Mejoras en documentación**
   - Crear tutoriales y manuales de usuario para facilitar la adopción de la localización.

## Descargo de Responsabilidad

Esta localización se proporciona "tal cual", sin garantías de ningún tipo, expresas o implícitas. El uso de esta localización es bajo tu propia responsabilidad. Binaural C.A. no se hace responsable por el uso indebido del software o por incumplimientos legales derivados de su implementación.

---

Queremos dar un especial agradecimiento a las personas que han colaborado con este proyecto a lo largo de todos estos años, algunos ya no forman parte directa de nuestro equipo pero han aportado a este proyecto y queremos hacer una valiosa mención:

- Daniela Gomez : [@DanielaGomezR93](https://github.com/DanielaGomezR93)
- Anderson Armeya : [@andyengit](https://github.com/andyengit)
- Miguel Gozaine : [@miguel-binaural](https://github.com/miguel-binaural)
- Carlos Linarez : [@Carlos-Lin-Binaural](https://github.com/Carlos-Lin-Binaural)
- Yeison Asuaje : [@yeisonasuaje](https://github.com/yeisonasuaje)
- Ana Paulina Calles : [@binapaulina](https://github.com/binapaulina)
- Bryan Garcia : [@AlebgDev](https://github.com/AlebgDev)
- Ysabel Godoy : [@ysabelgodoydelgado](https://github.com/ysabelgodoydelgado)
- David Aldana : [@bin-daldana](https://github.com/bin-daldana)
- Mauricio Istúriz : [@isturizbinaural](https://github.com/isturizbinaural) / [@isturiz](https://github.com/isturiz)
- Rubén Gonzalez : [@rsgg04](https://github.com/rsgg04)
- David Mendoza : [@deardavidBinaural](https://github.com/deardavidBinaural)
- Omar Yépez : [@OmarYepez29](https://github.com/OmarYepez29)
- Mariuska Parra : [@Mariuskaparra](https://github.com/Mariuskaparra)
- Valmore Canelon : [@valmorec](https://github.com/valmorec)
- Raiver Figueroa : [@raiver28](https://github.com/raiver28)
- Manuel Guerrero : [@manuelgc1201](https://github.com/manuelgc1201)


Y todas aquellas personas de nuestro equipo interno quienes de alguna y otra forma han colaborado con nuestro equipo.

---

¡Gracias por ser parte de este proyecto y por contribuir al crecimiento tecnológico de Venezuela! Si tienes preguntas o necesitas ayuda, no dudes en contactarnos.
