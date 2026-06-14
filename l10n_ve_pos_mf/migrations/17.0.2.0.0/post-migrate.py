# -*- coding: utf-8 -*-
"""
Post-migration script for l10n_ve_pos_mf 17.0.2.0.0
========================================================

Este script se ejecuta DESPUÉS de actualizar el módulo l10n_ve_pos_mf.

OBJETIVO:
---------
Validar que todos los campos migrados están correctamente configurados y
proporcionar un reporte de configuración para el administrador.

ACCIONES:
---------
1. Verificar que los campos fiscal_code y code_fiscal_printer existen
2. Reportar configuración actual de máquinas fiscales
3. Sugerir acciones de limpieza si l10n_ve_iot_mf ya no es necesario

NOTAS:
------
- Este script NO modifica datos, solo reporta el estado
- Ayuda a identificar configuraciones incompletas o errores de migración
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Validación post-migración de l10n_ve_pos_mf
    """
    _logger.info("=" * 80)
    _logger.info("POST-MIGRATION: l10n_ve_pos_mf version 17.0.2.0.0")
    _logger.info("=" * 80)

    # 1. Verificar campos críticos
    _logger.info("\n[1/4] Verificando campos críticos...")
    
    required_fields = {
        'account_tax': ['fiscal_code'],
        'pos_payment_method': ['code_fiscal_printer'],
        'pos_config': ['serial_machine', 'flag_21', 'traditional_line', 'has_cashbox']
    }
    
    all_fields_ok = True
    
    for table, fields in required_fields.items():
        for field in fields:
            cr.execute(f"""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = '{table}' AND column_name = '{field}'
            """)
            exists = cr.fetchone()
            
            if exists:
                _logger.info(f"  ✓ {table}.{field} existe")
            else:
                _logger.error(f"  ✗ {table}.{field} NO EXISTE - ERROR DE MIGRACIÓN")
                all_fields_ok = False

    # 2. Reporte de configuración de impuestos
    _logger.info("\n[2/4] Reporte de configuración de impuestos (fiscal_code)...")
    cr.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN fiscal_code IS NOT NULL AND fiscal_code != 0 THEN 1 END) as configured,
            COUNT(CASE WHEN fiscal_code IS NULL OR fiscal_code = 0 THEN 1 END) as not_configured
        FROM account_tax
        WHERE active = true
    """)
    tax_stats = cr.fetchone()
    
    if tax_stats:
        _logger.info(f"  Total impuestos activos: {tax_stats[0]}")
        _logger.info(f"  ✓ Configurados: {tax_stats[1]}")
        _logger.info(f"  ⚠ Sin configurar: {tax_stats[2]}")
        
        if tax_stats[2] > 0:
            _logger.warning("\n  ACCIÓN REQUERIDA:")
            _logger.warning("  Debes configurar el campo 'Código Fiscal (MF)' en los impuestos")
            _logger.warning("  sin configurar. Valores sugeridos:")
            _logger.warning("    0 = Exento")
            _logger.warning("    1 = IVA General (16%)")
            _logger.warning("    2 = IVA Reducido (8%)")
            _logger.warning("    3 = IVA Adicional")

    # 3. Reporte de configuración de métodos de pago
    _logger.info("\n[3/4] Reporte de métodos de pago (code_fiscal_printer)...")
    cr.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN code_fiscal_printer IS NOT NULL THEN 1 END) as configured,
            COUNT(CASE WHEN code_fiscal_printer IS NULL THEN 1 END) as not_configured
        FROM pos_payment_method
    """)
    payment_stats = cr.fetchone()
    
    if payment_stats:
        _logger.info(f"  Total métodos de pago: {payment_stats[0]}")
        _logger.info(f"  ✓ Configurados: {payment_stats[1]}")
        _logger.info(f"  ⚠ Sin configurar: {payment_stats[2]}")
        
        if payment_stats[2] > 0:
            _logger.warning("\n  ACCIÓN REQUERIDA:")
            _logger.warning("  Debes configurar 'Code fiscal printer' (01-24) en los métodos")
            _logger.warning("  de pago sin configurar.")

    # 4. Reporte de pos.config con máquinas fiscales
    _logger.info("\n[4/4] Reporte de puntos de venta con máquina fiscal...")
    cr.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN serial_machine IS NOT NULL AND serial_machine != '' THEN 1 END) as with_mf,
            COUNT(CASE WHEN serial_machine IS NULL OR serial_machine = '' THEN 1 END) as without_mf
        FROM pos_config
    """)
    pos_stats = cr.fetchone()
    
    if pos_stats:
        _logger.info(f"  Total puntos de venta: {pos_stats[0]}")
        _logger.info(f"  ✓ Con máquina fiscal: {pos_stats[1]}")
        _logger.info(f"  ℹ Sin máquina fiscal: {pos_stats[2]}")

    # Verificar si l10n_ve_iot_mf todavía está instalado
    _logger.info("\n[CLEANUP] Verificando módulo l10n_ve_iot_mf...")
    cr.execute("""
        SELECT state FROM ir_module_module
        WHERE name = 'l10n_ve_iot_mf'
    """)
    old_module = cr.fetchone()
    
    if old_module and old_module[0] in ('installed', 'to upgrade'):
        _logger.warning("\n" + "!" * 80)
        _logger.warning("ATENCIÓN: El módulo l10n_ve_iot_mf todavía está instalado")
        _logger.warning("!" * 80)
        _logger.warning("\nAhora que l10n_ve_pos_mf tiene los campos fiscal_code y")
        _logger.warning("code_fiscal_printer integrados, puedes desinstalar l10n_ve_iot_mf")
        _logger.warning("si ya NO usas el IoT Box para la máquina fiscal.")
        _logger.warning("\nPASOS PARA DESINSTALAR l10n_ve_iot_mf:")
        _logger.warning("  1. Ir a Aplicaciones")
        _logger.warning("  2. Buscar 'l10n_ve_iot_mf'")
        _logger.warning("  3. Hacer clic en 'Desinstalar'")
        _logger.warning("\nNOTA: Los datos de fiscal_code y code_fiscal_printer se preservarán.\n")
    else:
        _logger.info("  ✓ l10n_ve_iot_mf no está instalado (migración limpia)")

    # Resumen final
    _logger.info("\n" + "=" * 80)
    if all_fields_ok:
        _logger.info("✓ MIGRACIÓN COMPLETADA EXITOSAMENTE")
    else:
        _logger.error("✗ MIGRACIÓN COMPLETADA CON ERRORES")
        _logger.error("  Revisa los errores arriba y contacta a soporte técnico")
    _logger.info("=" * 80)
    
    _logger.info("\nPRÓXIMOS PASOS:")
    _logger.info("  1. Configurar fiscal_code en impuestos (si no están configurados)")
    _logger.info("  2. Configurar code_fiscal_printer en métodos de pago")
    _logger.info("  3. Configurar serial_machine en pos.config para las cajas con MF")
    _logger.info("  4. Probar conexión con máquina fiscal usando Web Serial API")
    _logger.info("  5. (Opcional) Desinstalar l10n_ve_iot_mf si ya no usas IoT Box\n")
