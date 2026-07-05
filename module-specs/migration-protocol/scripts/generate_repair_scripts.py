#!/usr/bin/env python3
"""
Genera los scripts SQL de reparación de ir_model_data para binaural_location.

Uso:
    python3 generate_repair_scripts.py <path_a_odoo-venezuela-17>

Regenera:
    fix_country_state_xmlids.sql
    fix_municipality_xmlids.sql

Contexto (ver MIGRATION_PROTOCOL.md sección "Hallazgo #3"):
Los backups de Odoo.sh de varios clientes tienen registros de
`res.country.state` y `res.country.municipality` con los VALORES correctos
pero SIN el `ir_model_data` (mapeo XML ID -> ID de registro) que el módulo
`binaural_location` espera encontrar. Al ejecutar `-u` sobre cualquier
módulo que fuerce la re-carga de estos datos (por drift de esquema en
otros módulos), Odoo intenta re-crear estos registros y falla por
violación de constraint UNIQUE (código de estado/nombre de municipio
duplicado).

Estos scripts insertan los `ir_model_data` faltantes buscando el registro
existente por su valor (code para estados, name+state para municipios) y
son 100% idempotentes (usan NOT EXISTS).
"""
import re
import sys
from pathlib import Path


def generate_state_fix(repo_path: Path, output_path: Path):
    xml_file = repo_path / "integra-addons-17" / "binaural_location" / "data" / "res_country_state_data.xml"
    content = xml_file.read_text()
    records = re.findall(
        r'<record id="([^"]+)" model="res.country.state">\s*'
        r'<field name="name">([^<]+)</field>\s*'
        r'<field name="code">([^<]+)</field>',
        content,
    )
    with open(output_path, "w") as f:
        f.write(f"-- {len(records)} estados a verificar/reparar (generado automáticamente)\n")
        for xml_id, name, code in records:
            f.write(f"""
INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', '{xml_id}', 'res.country.state', s.id, true, now(), now(), 1, 1
FROM res_country_state s
WHERE s.country_id = 238 AND s.code = '{code}'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='{xml_id}'
);
""")
    print(f"Generados {len(records)} estados -> {output_path}")


def generate_municipality_fix(repo_path: Path, output_path: Path):
    xml_file = repo_path / "integra-addons-17" / "binaural_location" / "data" / "res_country_municipality_data.xml"
    content = xml_file.read_text()
    records = re.findall(
        r"<record id=\"([^\"]+)\" model=\"res\.country\.municipality\">\s*"
        r"<field name=\"name\">([^<]+)</field>\s*"
        r"<field name=\"code\">[^<]*</field>\s*"
        r"<field name=\"state_id\"[^>]*ref\('([^']+)'\)",
        content,
    )
    with open(output_path, "w") as f:
        f.write(f"-- {len(records)} municipios a verificar/reparar (generado automáticamente)\n")
        for xml_id, name, state_ref in records:
            name_escaped = name.replace("'", "''")
            f.write(f"""
INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', '{xml_id}', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='{state_ref}' AND smd.res_id = s.id
WHERE m.name = '{name_escaped}'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='{xml_id}'
);
""")
    print(f"Generados {len(records)} municipios -> {output_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python3 generate_repair_scripts.py <path_a_directorio_src>")
        sys.exit(1)

    src_path = Path(sys.argv[1])
    out_dir = Path(__file__).parent

    generate_state_fix(src_path, out_dir / "fix_country_state_xmlids.sql")
    generate_municipality_fix(src_path, out_dir / "fix_municipality_xmlids.sql")
