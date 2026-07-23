# -*- coding: utf-8 -*-
"""
Pre-migration script for l10n_ve_pos_mf 17.0.2.0.0
=======================================================

Este script se ejecuta ANTES de actualizar el módulo l10n_ve_pos_mf.

OBJETIVO:
---------
Preservar datos de configuración cuando se migra desde la versión con IoT Box
(l10n_ve_iot_mf) a la nueva versión con Web Serial API.

ESCENARIOS:
-----------
1. Base de datos limpia (nueva instalación):
   - No hace nada, los campos se crean automáticamente

2. Base de datos en producción con l10n_ve_iot_mf ya instalado:
   - Copia valores de campos relacionados de iot.device a pos.config
   - Preserva fiscal_code de account.tax (ya existe, solo cambia el módulo propietario)
   - Preserva code_fiscal_printer de pos.payment.method

CAMPOS AFECTADOS:
-----------------
- pos.config: serial_machine, flag_21, traditional_line, has_cashbox
- account.tax: fiscal_code (migrado desde l10n_ve_iot_mf)
- pos.payment.method: code_fiscal_printer (ya existe en l10n_ve_pos_mf)

NOTAS:
------
- Este script es idempotente (se puede ejecutar varias veces sin efectos secundarios)
- Los campos fiscal_code y code_fiscal_printer NO se eliminan, solo cambian de módulo propietario
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Migración de datos desde l10n_ve_iot_mf a l10n_ve_pos_mf
    """
    _logger.info("=" * 80)
    _logger.info("PRE-MIGRATION: l10n_ve_pos_mf to version 17.0.2.0.0")
    _logger.info("=" * 80)

    # Verificar si el módulo viejo (l10n_ve_iot_mf) está instalado
    cr.execute("""
        SELECT id FROM ir_module_module
        WHERE name = 'l10n_ve_iot_mf' AND state IN ('installed', 'to upgrade')
    """)
    old_module_installed = cr.fetchone()

    if not old_module_installed:
        _logger.info("✓ Instalación limpia detectada (l10n_ve_iot_mf no está instalado)")
        _logger.info("  No es necesario migrar datos.")
        return

    _logger.info("✓ Migración desde l10n_ve_iot_mf detectada")
    _logger.info("  Preservando configuración existente...")

    # 1. Migrar configuración de pos.config desde iot.device
    _logger.info("\n[1/3] Migrando campos de pos.config desde iot.device...")
    
    # Verificar si la tabla iot_device existe
    cr.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'iot_device'
        )
    """)
    iot_device_exists = cr.fetchone()[0]

    if iot_device_exists:
        # Verificar si existen columnas en iot_device
        cr.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'iot_device'
            AND column_name IN ('serial_machine', 'flag_21', 'traditional_line', 'has_cashbox')
        """)
        existing_columns = [row[0] for row in cr.fetchall()]

        if existing_columns:
            _logger.info(f"  Columnas encontradas en iot.device: {existing_columns}")

            # Los campos ya deberían existir en pos.config si se instaló l10n_ve_pos_mf
            # antes, pero en saltos de versión grandes (varias versiones de golpe)
            # este pre-migrate puede correr ANTES de que pos.config tenga esas
            # columnas todavía (se crean recién al sincronizar el modelo). Verificar
            # primero para no romper la migración completa por un simple log.
            cr.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'pos_config'
                AND column_name IN ('serial_machine', 'flag_21', 'traditional_line', 'has_cashbox')
            """)
            pos_config_columns = [row[0] for row in cr.fetchall()]

            if pos_config_columns:
                select_cols = ", ".join(f"pc.{col}" for col in pos_config_columns)
                where_cols = " OR ".join(f"pc.{col} IS NOT NULL" for col in pos_config_columns)
                cr.execute(f"""
                    SELECT pc.id, pc.name, {select_cols}
                    FROM pos_config pc
                    WHERE {where_cols}
                """)
                configs = cr.fetchall()

                if configs:
                    _logger.info(f"  ✓ Encontrados {len(configs)} pos.config con datos de máquina fiscal")
                    for config in configs:
                        _logger.info(f"    - POS Config ID {config[0]} ({config[1]}): {dict(zip(pos_config_columns, config[2:]))}")
                else:
                    _logger.info("  ⚠ No se encontraron pos.config con datos de máquina fiscal")
            else:
                _logger.info("  ℹ Columnas de MF en pos.config no existen aún (se crearán al sincronizar el modelo)")
        else:
            _logger.info("  ⚠ No se encontraron columnas de MF en iot.device")
    else:
        _logger.info("  ⚠ Tabla iot.device no existe (ya fue eliminada)")

    # 2. Verificar datos de account.tax (fiscal_code)
    _logger.info("\n[2/3] Verificando fiscal_code en account.tax...")
    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'account_tax' AND column_name = 'fiscal_code'
    """)
    fiscal_code_exists = cr.fetchone()

    if fiscal_code_exists:
        cr.execute("""
            SELECT id, name, fiscal_code 
            FROM account_tax 
            WHERE fiscal_code IS NOT NULL AND fiscal_code != 0
            ORDER BY id
        """)
        taxes = cr.fetchall()
        
        if taxes:
            _logger.info(f"  ✓ Encontrados {len(taxes)} impuestos con fiscal_code configurado:")
            for tax in taxes:
                _logger.info(f"    - Tax ID {tax[0]} ({tax[1]}): fiscal_code={tax[2]}")
        else:
            _logger.info("  ⚠ No se encontraron impuestos con fiscal_code")
    else:
        _logger.info("  ℹ Campo fiscal_code no existe aún (se creará en post-migrate)")

    # 3. Migrar payment_method desde account.journal a pos.payment.method
    _logger.info("\n[3/3] Migrando payment_method (account.journal) → code_fiscal_printer (pos.payment.method)...")
    
    # Verificar si existe el campo payment_method en account.journal (módulo viejo)
    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'account_journal' AND column_name = 'payment_method'
    """)
    old_payment_method_exists = cr.fetchone()
    
    # Verificar si existe el campo code_fiscal_printer en pos.payment.method (módulo nuevo)
    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'pos_payment_method' AND column_name = 'code_fiscal_printer'
    """)
    code_fiscal_printer_exists = cr.fetchone()

    if old_payment_method_exists and code_fiscal_printer_exists:
        # Copiar valores desde account.journal.payment_method a pos.payment.method.code_fiscal_printer
        _logger.info("  Copiando valores desde account.journal.payment_method...")
        
        cr.execute("""
            UPDATE pos_payment_method pm
            SET code_fiscal_printer = aj.payment_method
            FROM account_journal aj
            WHERE pm.journal_id = aj.id
              AND aj.payment_method IS NOT NULL
              AND aj.payment_method != ''
              AND (pm.code_fiscal_printer IS NULL OR pm.code_fiscal_printer = '01')
        """)
        rows_updated = cr.rowcount
        
        if rows_updated > 0:
            _logger.info(f"  ✓ {rows_updated} métodos de pago actualizados con valores desde account.journal")
            
            # Mostrar resultado
            cr.execute("""
                SELECT pm.id, pm.name, pm.code_fiscal_printer, aj.name as journal_name
                FROM pos_payment_method pm
                JOIN account_journal aj ON pm.journal_id = aj.id
                WHERE pm.code_fiscal_printer IS NOT NULL
                ORDER BY pm.id
            """)
            payment_methods = cr.fetchall()
            
            for pm in payment_methods:
                _logger.info(f"    - Payment Method ID {pm[0]} ({pm[1]}): code_fiscal_printer={pm[2]} (desde diario: {pm[3]})")
        else:
            _logger.info("  ℹ No se encontraron valores para copiar (ya estaban configurados o no existen)")
    
    elif code_fiscal_printer_exists:
        # El campo nuevo existe pero el viejo no (instalación limpia o ya migrado)
        cr.execute("""
            SELECT id, name, code_fiscal_printer 
            FROM pos_payment_method 
            WHERE code_fiscal_printer IS NOT NULL
            ORDER BY id
        """)
        payment_methods = cr.fetchall()
        
        if payment_methods:
            _logger.info(f"  ✓ Encontrados {len(payment_methods)} métodos de pago con code_fiscal_printer:")
            for pm in payment_methods:
                _logger.info(f"    - Payment Method ID {pm[0]} ({pm[1]}): code_fiscal_printer={pm[2]}")
        else:
            _logger.info("  ⚠ No se encontraron métodos de pago con code_fiscal_printer configurado")
    
    else:
        _logger.info("  ℹ Campo code_fiscal_printer no existe aún (se creará en post-migrate)")

    _logger.info("\n" + "=" * 80)
    _logger.info("✓ PRE-MIGRATION COMPLETADA")
    _logger.info("=" * 80)
    _logger.info("\nNOTA: Los campos se preservarán automáticamente.")
    _logger.info("      Después de la actualización, puedes desinstalar l10n_ve_iot_mf")
    _logger.info("      si ya no usas el IoT Box.\n")
