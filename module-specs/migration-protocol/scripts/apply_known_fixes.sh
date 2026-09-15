#!/bin/bash
# Aplica los fixes de drift conocidos (ver MIGRATION_PROTOCOL.md) sobre una
# base de datos de cliente ANTES de correr el upgrade de módulos fiscales.
#
# IMPORTANTE (v2.0): antes de correr esto, verifica que ya seguiste la
# sección 0 del protocolo (submodules del cliente para integra-addons/
# third-party-addons, NO el checkout compartido). Los fixes #1 y #2 de este
# script corresponden al Hallazgo #3 RETRACTADO — solo son necesarios si tu
# cliente específico SÍ tiene `binaural_location` en su pin real de
# integra-addons (poco común). Verifica primero con:
#   ls src/custom/<cliente>/integra-addons/binaural_location/__manifest__.py
# Si no existe, sáltate los pasos 1 y 2 (no aplican).
#
# Uso:
#   ./apply_known_fixes.sh <container> <db_name> <db_host> <db_port> <db_user> <db_password>
#
# Ejemplo:
#   ./apply_known_fixes.sh odoo-dialca dialca host.docker.internal 5433 odoo odoo

set -e

CONTAINER="${1:?Falta nombre de contenedor}"
DB_NAME="${2:?Falta nombre de base de datos}"
DB_HOST="${3:-host.docker.internal}"
DB_PORT="${4:-5433}"
DB_USER="${5:-odoo}"
DB_PASSWORD="${6:-odoo}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Aplicando fixes conocidos en ${DB_NAME} (contenedor ${CONTAINER}) ==="

psql_exec() {
    docker exec -e PGPASSWORD="${DB_PASSWORD}" "${CONTAINER}" \
        psql --host "${DB_HOST}" --port "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" "$@"
}

echo "--- 1. [DEPRECADO - Hallazgo #3 retractado] Reparando ir_model_data de res.country.state ---"
echo "    (solo aplica si tu cliente SI tiene binaural_location en su pin real; ver nota arriba)"
docker cp "${SCRIPT_DIR}/fix_country_state_xmlids.sql" "${CONTAINER}:/tmp/fix_country_state_xmlids.sql"
psql_exec -f /tmp/fix_country_state_xmlids.sql | grep -c "INSERT 0 1" || true

echo "--- 2. [DEPRECADO - Hallazgo #3 retractado] Reparando ir_model_data de res.country.municipality ---"
docker cp "${SCRIPT_DIR}/fix_municipality_xmlids.sql" "${CONTAINER}:/tmp/fix_municipality_xmlids.sql"
psql_exec -f /tmp/fix_municipality_xmlids.sql | grep -c "INSERT 0 1" || true

echo "--- 3. Desactivando vistas huérfanas legacy IoT de l10n_ve_pos_mf (si existen) ---"
psql_exec -At -c "
UPDATE ir_ui_view SET active = false
WHERE id IN (
    SELECT v.id FROM ir_ui_view v
    JOIN ir_model_data d ON d.model='ir.ui.view' AND d.res_id=v.id
    WHERE d.module='l10n_ve_pos_mf'
    AND d.name IN ('pos_config_view_form_inherit', 'l10n_ve_pos_mf_res_config_settings_view_form_inherit_pos_iot')
);
"

echo ""
echo "=== Fixes aplicados. Ahora corre el upgrade de módulos: ==="
echo "docker exec -u root ${CONTAINER} odoo --stop-after-init -d ${DB_NAME} \\"
echo "    -u l10n_ve_payment_extension,l10n_ve_pos,l10n_ve_iot_mf,l10n_ve_pos_mf,l10n_ve_mf_base"
echo ""
echo "Si el cliente tiene módulos custom propios de MF (ej. <cliente>_mf), agrégalos al final."
echo ""
echo "=== IMPORTANTE: tras cualquier comando '-u root', corregir permisos de filestore: ==="
echo "docker exec -u root ${CONTAINER} chown -R odoo:odoo /home/odoo/data"
echo "docker restart ${CONTAINER}"
