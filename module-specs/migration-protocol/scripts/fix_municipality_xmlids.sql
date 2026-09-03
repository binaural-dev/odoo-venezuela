-- 334 municipios a verificar/reparar

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_1', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_1' AND smd.res_id = s.id
WHERE m.name = 'Libertador'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_1'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_2', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_2' AND smd.res_id = s.id
WHERE m.name = 'Alto Orinoco'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_2'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_3', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_2' AND smd.res_id = s.id
WHERE m.name = 'San Fernando de Atabapo'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_3'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_4', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_2' AND smd.res_id = s.id
WHERE m.name = 'Atures'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_4'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_5', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_2' AND smd.res_id = s.id
WHERE m.name = 'Autana'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_5'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_6', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_2' AND smd.res_id = s.id
WHERE m.name = 'Guainia'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_6'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_7', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_2' AND smd.res_id = s.id
WHERE m.name = 'Manapiare'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_7'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_8', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_2' AND smd.res_id = s.id
WHERE m.name = 'San Carlos de Rio Negro'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_8'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_9', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_3' AND smd.res_id = s.id
WHERE m.name = 'Anaco'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_9'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_10', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_3' AND smd.res_id = s.id
WHERE m.name = 'Aragua'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_10'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_11', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_3' AND smd.res_id = s.id
WHERE m.name = 'San Juan de Capistrano'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_11'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_12', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_3' AND smd.res_id = s.id
WHERE m.name = 'Simon Bolivar'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_12'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_13', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_3' AND smd.res_id = s.id
WHERE m.name = 'Manuel Ezequiel Bruzal'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_13'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_14', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_3' AND smd.res_id = s.id
WHERE m.name = 'Juan Manuel Cajigal'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_14'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_15', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_3' AND smd.res_id = s.id
WHERE m.name = 'Francisco del Carmen Carvajal'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_15'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_16', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_3' AND smd.res_id = s.id
WHERE m.name = 'Pedro Maria Freites'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_16'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_17', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_3' AND smd.res_id = s.id
WHERE m.name = 'General Sir Arthur Mc Gregor'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_17'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_18', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_3' AND smd.res_id = s.id
WHERE m.name = 'San Jose de Guanipa'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_18'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_19', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_3' AND smd.res_id = s.id
WHERE m.name = 'Guanta'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_19'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_20', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_3' AND smd.res_id = s.id
WHERE m.name = 'Independencia'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_20'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_21', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_3' AND smd.res_id = s.id
WHERE m.name = 'Libertad'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_21'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_22', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_3' AND smd.res_id = s.id
WHERE m.name = 'Lic. Diego Bautista Urbaneja'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_22'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_23', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_3' AND smd.res_id = s.id
WHERE m.name = 'Francisco de Miranda'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_23'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_24', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_3' AND smd.res_id = s.id
WHERE m.name = 'Jose Gregorio Monagas'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_24'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_25', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_3' AND smd.res_id = s.id
WHERE m.name = 'Fernando Peñalver'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_25'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_26', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_3' AND smd.res_id = s.id
WHERE m.name = 'Piritu'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_26'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_27', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_3' AND smd.res_id = s.id
WHERE m.name = 'Santa Ana'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_27'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_28', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_3' AND smd.res_id = s.id
WHERE m.name = 'Simon Rodriguez'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_28'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_29', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_3' AND smd.res_id = s.id
WHERE m.name = 'Juan Antonio Sotillo'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_29'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_30', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_4' AND smd.res_id = s.id
WHERE m.name = 'Achaguas'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_30'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_31', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_4' AND smd.res_id = s.id
WHERE m.name = 'Biruaca'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_31'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_32', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_4' AND smd.res_id = s.id
WHERE m.name = 'Muñoz'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_32'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_33', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_4' AND smd.res_id = s.id
WHERE m.name = 'Paez'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_33'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_34', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_4' AND smd.res_id = s.id
WHERE m.name = 'Pedro Camejo'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_34'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_35', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_4' AND smd.res_id = s.id
WHERE m.name = 'Rómulo Gallegos'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_35'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_36', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_4' AND smd.res_id = s.id
WHERE m.name = 'San Fernando'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_36'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_37', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_5' AND smd.res_id = s.id
WHERE m.name = 'Bolivar'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_37'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_38', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_5' AND smd.res_id = s.id
WHERE m.name = 'Camatagua'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_38'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_39', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_5' AND smd.res_id = s.id
WHERE m.name = 'Girardot'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_39'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_40', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_5' AND smd.res_id = s.id
WHERE m.name = 'José Angel Lamas'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_40'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_41', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_5' AND smd.res_id = s.id
WHERE m.name = 'José Félix Ribas'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_41'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_42', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_5' AND smd.res_id = s.id
WHERE m.name = 'José Rafael Revenga'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_42'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_43', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_5' AND smd.res_id = s.id
WHERE m.name = 'Libertador'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_43'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_44', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_5' AND smd.res_id = s.id
WHERE m.name = 'Mario Briceño Iragorry'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_44'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_45', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_5' AND smd.res_id = s.id
WHERE m.name = 'San Casimiro'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_45'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_46', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_5' AND smd.res_id = s.id
WHERE m.name = 'San Sebastián'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_46'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_47', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_5' AND smd.res_id = s.id
WHERE m.name = 'Santiago Mariño'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_47'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_48', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_5' AND smd.res_id = s.id
WHERE m.name = 'Santos Michelena'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_48'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_49', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_5' AND smd.res_id = s.id
WHERE m.name = 'Sucre'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_49'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_50', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_5' AND smd.res_id = s.id
WHERE m.name = 'Tovar'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_50'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_51', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_5' AND smd.res_id = s.id
WHERE m.name = 'Urdaneta'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_51'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_52', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_5' AND smd.res_id = s.id
WHERE m.name = 'Zamora'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_52'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_53', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_5' AND smd.res_id = s.id
WHERE m.name = 'Ocumare de la Costa de Oro'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_53'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_54', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_5' AND smd.res_id = s.id
WHERE m.name = 'Francisco Linares Alcantara'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_54'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_55', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_6' AND smd.res_id = s.id
WHERE m.name = 'Alberto Arvelo Torrealba'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_55'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_56', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_6' AND smd.res_id = s.id
WHERE m.name = 'Antonio Jose de Sucre'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_56'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_57', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_6' AND smd.res_id = s.id
WHERE m.name = 'Arismendi'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_57'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_58', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_6' AND smd.res_id = s.id
WHERE m.name = 'Barinas'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_58'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_59', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_6' AND smd.res_id = s.id
WHERE m.name = 'Bolivar'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_59'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_60', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_6' AND smd.res_id = s.id
WHERE m.name = 'Cruz Paredes'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_60'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_61', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_6' AND smd.res_id = s.id
WHERE m.name = 'Ezequiel Zamora'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_61'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_62', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_6' AND smd.res_id = s.id
WHERE m.name = 'Obispos'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_62'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_63', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_6' AND smd.res_id = s.id
WHERE m.name = 'Pedraza'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_63'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_64', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_6' AND smd.res_id = s.id
WHERE m.name = 'Rojas'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_64'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_65', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_6' AND smd.res_id = s.id
WHERE m.name = 'Sosa'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_65'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_66', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_7' AND smd.res_id = s.id
WHERE m.name = 'Caroní'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_66'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_67', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_7' AND smd.res_id = s.id
WHERE m.name = 'Cedeño'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_67'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_68', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_7' AND smd.res_id = s.id
WHERE m.name = 'El Callao'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_68'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_69', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_7' AND smd.res_id = s.id
WHERE m.name = 'Gran Sabana'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_69'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_70', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_7' AND smd.res_id = s.id
WHERE m.name = 'Heres'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_70'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_71', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_7' AND smd.res_id = s.id
WHERE m.name = 'Piar'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_71'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_72', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_7' AND smd.res_id = s.id
WHERE m.name = 'Raul Leoni'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_72'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_73', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_7' AND smd.res_id = s.id
WHERE m.name = 'Roscio'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_73'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_74', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_7' AND smd.res_id = s.id
WHERE m.name = 'Sifontes'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_74'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_75', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_7' AND smd.res_id = s.id
WHERE m.name = 'Sucre'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_75'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_76', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_7' AND smd.res_id = s.id
WHERE m.name = 'Padre Pedro Chien'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_76'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_77', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_8' AND smd.res_id = s.id
WHERE m.name = 'Bejuma'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_77'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_78', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_8' AND smd.res_id = s.id
WHERE m.name = 'Carlos Arvelo'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_78'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_79', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_8' AND smd.res_id = s.id
WHERE m.name = 'Diego Ibarra'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_79'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_80', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_8' AND smd.res_id = s.id
WHERE m.name = 'Guacara'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_80'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_81', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_8' AND smd.res_id = s.id
WHERE m.name = 'Juan Jose Mora'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_81'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_82', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_8' AND smd.res_id = s.id
WHERE m.name = 'Libertador'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_82'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_83', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_8' AND smd.res_id = s.id
WHERE m.name = 'Los Guayos'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_83'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_84', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_8' AND smd.res_id = s.id
WHERE m.name = 'Miranda'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_84'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_85', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_8' AND smd.res_id = s.id
WHERE m.name = 'Montalban'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_85'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_86', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_8' AND smd.res_id = s.id
WHERE m.name = 'Naguanagua'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_86'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_87', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_8' AND smd.res_id = s.id
WHERE m.name = 'Puerto Cabello'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_87'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_88', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_8' AND smd.res_id = s.id
WHERE m.name = 'San Diego'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_88'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_89', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_8' AND smd.res_id = s.id
WHERE m.name = 'San Joaquin'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_89'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_90', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_8' AND smd.res_id = s.id
WHERE m.name = 'Valencia'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_90'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_91', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_9' AND smd.res_id = s.id
WHERE m.name = 'Anzoategui'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_91'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_92', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_9' AND smd.res_id = s.id
WHERE m.name = 'Falcon'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_92'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_93', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_9' AND smd.res_id = s.id
WHERE m.name = 'Girardot'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_93'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_94', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_9' AND smd.res_id = s.id
WHERE m.name = 'Lima Blanco'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_94'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_95', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_9' AND smd.res_id = s.id
WHERE m.name = 'Pao de San Juan Bautista'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_95'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_96', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_9' AND smd.res_id = s.id
WHERE m.name = 'Ricaurte'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_96'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_97', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_9' AND smd.res_id = s.id
WHERE m.name = 'Rómulo Gallegos'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_97'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_98', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_9' AND smd.res_id = s.id
WHERE m.name = 'San Carlos'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_98'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_99', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_9' AND smd.res_id = s.id
WHERE m.name = 'Tinaco'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_99'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_100', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_10' AND smd.res_id = s.id
WHERE m.name = 'Antonio Díaz'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_100'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_101', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_10' AND smd.res_id = s.id
WHERE m.name = 'Casacoima'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_101'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_102', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_10' AND smd.res_id = s.id
WHERE m.name = 'Pedernales'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_102'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_103', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_10' AND smd.res_id = s.id
WHERE m.name = 'Tucupita'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_103'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_104', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_11' AND smd.res_id = s.id
WHERE m.name = 'Acosta'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_104'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_105', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_11' AND smd.res_id = s.id
WHERE m.name = 'Bolívar'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_105'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_106', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_11' AND smd.res_id = s.id
WHERE m.name = 'Buchivacoa'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_106'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_107', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_11' AND smd.res_id = s.id
WHERE m.name = 'Cacique Manaure'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_107'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_108', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_11' AND smd.res_id = s.id
WHERE m.name = 'Carirubana'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_108'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_109', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_11' AND smd.res_id = s.id
WHERE m.name = 'Colina'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_109'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_110', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_11' AND smd.res_id = s.id
WHERE m.name = 'Dabajuro'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_110'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_111', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_11' AND smd.res_id = s.id
WHERE m.name = 'Democracia'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_111'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_112', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_11' AND smd.res_id = s.id
WHERE m.name = 'Falcón'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_112'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_113', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_11' AND smd.res_id = s.id
WHERE m.name = 'Federación'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_113'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_114', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_11' AND smd.res_id = s.id
WHERE m.name = 'Jacura'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_114'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_115', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_11' AND smd.res_id = s.id
WHERE m.name = 'Los Taques'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_115'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_116', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_11' AND smd.res_id = s.id
WHERE m.name = 'Mauroa'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_116'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_117', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_11' AND smd.res_id = s.id
WHERE m.name = 'Miranda'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_117'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_118', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_11' AND smd.res_id = s.id
WHERE m.name = 'Monseñor Iturriza'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_118'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_119', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_11' AND smd.res_id = s.id
WHERE m.name = 'Palma sola'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_119'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_120', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_11' AND smd.res_id = s.id
WHERE m.name = 'Petit'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_120'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_121', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_11' AND smd.res_id = s.id
WHERE m.name = 'Píritu'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_121'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_122', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_11' AND smd.res_id = s.id
WHERE m.name = 'San Francisco'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_122'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_123', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_11' AND smd.res_id = s.id
WHERE m.name = 'Silva'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_123'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_124', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_11' AND smd.res_id = s.id
WHERE m.name = 'Sucre'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_124'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_125', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_11' AND smd.res_id = s.id
WHERE m.name = 'Tocópero'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_125'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_126', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_11' AND smd.res_id = s.id
WHERE m.name = 'Unión'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_126'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_127', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_11' AND smd.res_id = s.id
WHERE m.name = 'Urumaco'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_127'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_128', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_11' AND smd.res_id = s.id
WHERE m.name = 'Zamora'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_128'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_129', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_12' AND smd.res_id = s.id
WHERE m.name = 'Camaguán'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_129'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_130', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_12' AND smd.res_id = s.id
WHERE m.name = 'Chaguaramas'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_130'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_131', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_12' AND smd.res_id = s.id
WHERE m.name = 'El Socorro'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_131'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_132', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_12' AND smd.res_id = s.id
WHERE m.name = 'San Geronimo de Gayabal'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_132'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_133', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_12' AND smd.res_id = s.id
WHERE m.name = 'Leonardo Infante'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_133'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_134', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_12' AND smd.res_id = s.id
WHERE m.name = 'Las Mercades'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_134'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_135', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_12' AND smd.res_id = s.id
WHERE m.name = 'Mallado'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_135'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_136', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_12' AND smd.res_id = s.id
WHERE m.name = 'Francisco de Miranda'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_136'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_137', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_12' AND smd.res_id = s.id
WHERE m.name = 'Jose Tadeo Monagas'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_137'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_138', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_12' AND smd.res_id = s.id
WHERE m.name = 'Ortiz'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_138'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_139', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_12' AND smd.res_id = s.id
WHERE m.name = 'Jose Felix Ribas'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_139'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_140', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_12' AND smd.res_id = s.id
WHERE m.name = 'Juan German Roscio'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_140'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_141', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_12' AND smd.res_id = s.id
WHERE m.name = 'San Jose de Guaribe'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_141'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_142', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_12' AND smd.res_id = s.id
WHERE m.name = 'Santa Maria de Ipire'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_142'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_143', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_12' AND smd.res_id = s.id
WHERE m.name = 'Pedro Zaraza'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_143'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_144', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_13' AND smd.res_id = s.id
WHERE m.name = 'Andres Eloy Blanco'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_144'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_145', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_13' AND smd.res_id = s.id
WHERE m.name = 'Crespo'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_145'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_146', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_13' AND smd.res_id = s.id
WHERE m.name = 'Iribarren'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_146'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_147', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_13' AND smd.res_id = s.id
WHERE m.name = 'Jimenez'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_147'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_148', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_13' AND smd.res_id = s.id
WHERE m.name = 'Moran'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_148'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_149', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_13' AND smd.res_id = s.id
WHERE m.name = 'Palavecino'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_149'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_150', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_13' AND smd.res_id = s.id
WHERE m.name = 'Simón Planas'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_150'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_151', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_13' AND smd.res_id = s.id
WHERE m.name = 'Torres'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_151'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_152', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_13' AND smd.res_id = s.id
WHERE m.name = 'Urdaneta'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_152'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_153', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_14' AND smd.res_id = s.id
WHERE m.name = 'Alberto Adriani'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_153'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_154', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_14' AND smd.res_id = s.id
WHERE m.name = 'Andres Bello'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_154'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_155', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_14' AND smd.res_id = s.id
WHERE m.name = 'Antonio Pinto Salinas'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_155'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_156', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_14' AND smd.res_id = s.id
WHERE m.name = 'Aricagua'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_156'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_157', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_14' AND smd.res_id = s.id
WHERE m.name = 'Arzobispo Chacón'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_157'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_158', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_14' AND smd.res_id = s.id
WHERE m.name = 'Campo Elías'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_158'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_159', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_14' AND smd.res_id = s.id
WHERE m.name = 'Caracciolo Parra Olmedo'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_159'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_160', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_14' AND smd.res_id = s.id
WHERE m.name = 'Cardenal Quintero'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_160'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_161', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_14' AND smd.res_id = s.id
WHERE m.name = 'Guaraque'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_161'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_162', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_14' AND smd.res_id = s.id
WHERE m.name = 'Julio César Salas'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_162'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_163', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_14' AND smd.res_id = s.id
WHERE m.name = 'Justo Briceño'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_163'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_164', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_14' AND smd.res_id = s.id
WHERE m.name = 'Libertador'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_164'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_165', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_14' AND smd.res_id = s.id
WHERE m.name = 'Miranda'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_165'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_166', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_14' AND smd.res_id = s.id
WHERE m.name = 'Obispo Ramos de Lora'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_166'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_167', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_14' AND smd.res_id = s.id
WHERE m.name = 'Padre Noguera'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_167'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_168', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_14' AND smd.res_id = s.id
WHERE m.name = 'Pueblo Llano'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_168'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_169', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_14' AND smd.res_id = s.id
WHERE m.name = 'Rangel'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_169'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_170', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_14' AND smd.res_id = s.id
WHERE m.name = 'Rivas Dávila'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_170'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_171', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_14' AND smd.res_id = s.id
WHERE m.name = 'Santos Marquina'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_171'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_172', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_14' AND smd.res_id = s.id
WHERE m.name = 'Sucre'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_172'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_173', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_14' AND smd.res_id = s.id
WHERE m.name = 'Tovar'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_173'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_174', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_14' AND smd.res_id = s.id
WHERE m.name = 'Tulio Febres Cordero'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_174'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_175', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_14' AND smd.res_id = s.id
WHERE m.name = 'Zea'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_175'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_176', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_15' AND smd.res_id = s.id
WHERE m.name = 'Acevedo'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_176'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_177', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_15' AND smd.res_id = s.id
WHERE m.name = 'Andrés Bello'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_177'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_178', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_15' AND smd.res_id = s.id
WHERE m.name = 'Baruta'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_178'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_179', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_15' AND smd.res_id = s.id
WHERE m.name = 'Brión'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_179'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_180', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_15' AND smd.res_id = s.id
WHERE m.name = 'Buroz'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_180'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_181', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_15' AND smd.res_id = s.id
WHERE m.name = 'Carrizal'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_181'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_182', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_15' AND smd.res_id = s.id
WHERE m.name = 'Chacao'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_182'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_183', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_15' AND smd.res_id = s.id
WHERE m.name = 'Cristóbal Rojas'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_183'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_184', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_15' AND smd.res_id = s.id
WHERE m.name = 'El Hatillo'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_184'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_185', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_15' AND smd.res_id = s.id
WHERE m.name = 'Guaicaipuro'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_185'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_186', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_15' AND smd.res_id = s.id
WHERE m.name = 'Independencia'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_186'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_187', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_15' AND smd.res_id = s.id
WHERE m.name = 'Lander'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_187'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_188', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_15' AND smd.res_id = s.id
WHERE m.name = 'Los Salias'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_188'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_189', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_15' AND smd.res_id = s.id
WHERE m.name = 'Páez'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_189'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_190', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_15' AND smd.res_id = s.id
WHERE m.name = 'Paz Castillo'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_190'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_191', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_15' AND smd.res_id = s.id
WHERE m.name = 'Pedro Gual'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_191'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_192', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_15' AND smd.res_id = s.id
WHERE m.name = 'Plaza'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_192'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_193', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_15' AND smd.res_id = s.id
WHERE m.name = 'Simón Bolívar'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_193'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_194', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_15' AND smd.res_id = s.id
WHERE m.name = 'Sucre'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_194'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_195', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_15' AND smd.res_id = s.id
WHERE m.name = 'Urdaneta'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_195'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_196', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_15' AND smd.res_id = s.id
WHERE m.name = 'Zamora'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_196'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_197', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_16' AND smd.res_id = s.id
WHERE m.name = 'Acosta'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_197'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_198', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_16' AND smd.res_id = s.id
WHERE m.name = 'Aguasay'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_198'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_199', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_16' AND smd.res_id = s.id
WHERE m.name = 'Bolívar'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_199'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_200', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_16' AND smd.res_id = s.id
WHERE m.name = 'Caripe'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_200'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_201', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_16' AND smd.res_id = s.id
WHERE m.name = 'Cedeño'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_201'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_202', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_16' AND smd.res_id = s.id
WHERE m.name = 'Ezequiel Zamora'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_202'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_203', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_16' AND smd.res_id = s.id
WHERE m.name = 'Libertador'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_203'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_204', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_16' AND smd.res_id = s.id
WHERE m.name = 'Maturín'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_204'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_205', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_16' AND smd.res_id = s.id
WHERE m.name = 'Piar'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_205'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_206', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_16' AND smd.res_id = s.id
WHERE m.name = 'Punceres'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_206'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_207', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_16' AND smd.res_id = s.id
WHERE m.name = 'Santa Bárbara'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_207'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_208', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_16' AND smd.res_id = s.id
WHERE m.name = 'Sotillo'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_208'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_209', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_16' AND smd.res_id = s.id
WHERE m.name = 'Uracoa'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_209'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_210', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_17' AND smd.res_id = s.id
WHERE m.name = 'Antolín del Campo'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_210'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_211', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_17' AND smd.res_id = s.id
WHERE m.name = 'Arismendi'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_211'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_212', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_17' AND smd.res_id = s.id
WHERE m.name = 'Díaz'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_212'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_213', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_17' AND smd.res_id = s.id
WHERE m.name = 'García'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_213'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_214', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_17' AND smd.res_id = s.id
WHERE m.name = 'Gómez'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_214'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_215', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_17' AND smd.res_id = s.id
WHERE m.name = 'Maneiro'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_215'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_216', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_17' AND smd.res_id = s.id
WHERE m.name = 'Marcano'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_216'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_217', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_17' AND smd.res_id = s.id
WHERE m.name = 'Mariño'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_217'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_218', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_17' AND smd.res_id = s.id
WHERE m.name = 'Península de Macanao'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_218'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_219', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_17' AND smd.res_id = s.id
WHERE m.name = 'Tubores'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_219'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_220', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_17' AND smd.res_id = s.id
WHERE m.name = 'Villalba'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_220'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_221', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_18' AND smd.res_id = s.id
WHERE m.name = 'Agua Blanca'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_221'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_222', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_18' AND smd.res_id = s.id
WHERE m.name = 'Araure'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_222'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_223', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_18' AND smd.res_id = s.id
WHERE m.name = 'Esteller'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_223'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_224', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_18' AND smd.res_id = s.id
WHERE m.name = 'Guanare'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_224'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_225', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_18' AND smd.res_id = s.id
WHERE m.name = 'Guanarito'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_225'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_226', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_18' AND smd.res_id = s.id
WHERE m.name = 'Monseñor José Vicente de Unda'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_226'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_227', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_18' AND smd.res_id = s.id
WHERE m.name = 'Ospino'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_227'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_228', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_18' AND smd.res_id = s.id
WHERE m.name = 'Páez'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_228'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_229', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_18' AND smd.res_id = s.id
WHERE m.name = 'Papelón'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_229'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_230', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_18' AND smd.res_id = s.id
WHERE m.name = 'San Genaro de Boconoíto'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_230'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_231', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_18' AND smd.res_id = s.id
WHERE m.name = 'San Rafael de Onoto'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_231'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_232', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_18' AND smd.res_id = s.id
WHERE m.name = 'Santa Rosalía'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_232'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_233', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_18' AND smd.res_id = s.id
WHERE m.name = 'Sucre'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_233'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_234', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_18' AND smd.res_id = s.id
WHERE m.name = 'Turén'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_234'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_235', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_19' AND smd.res_id = s.id
WHERE m.name = 'Andrés Eloy Blanco'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_235'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_236', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_19' AND smd.res_id = s.id
WHERE m.name = 'Andrés Mata'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_236'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_237', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_19' AND smd.res_id = s.id
WHERE m.name = 'Arismendi'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_237'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_238', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_19' AND smd.res_id = s.id
WHERE m.name = 'Benítez'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_238'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_239', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_19' AND smd.res_id = s.id
WHERE m.name = 'Bermúdez'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_239'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_240', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_19' AND smd.res_id = s.id
WHERE m.name = 'Bolívar'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_240'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_241', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_19' AND smd.res_id = s.id
WHERE m.name = 'Cajigal'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_241'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_242', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_19' AND smd.res_id = s.id
WHERE m.name = 'Cruz Salmerón Acosta'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_242'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_243', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_19' AND smd.res_id = s.id
WHERE m.name = 'Libertador'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_243'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_244', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_19' AND smd.res_id = s.id
WHERE m.name = 'Mariño'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_244'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_245', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_19' AND smd.res_id = s.id
WHERE m.name = 'Mejía'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_245'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_246', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_19' AND smd.res_id = s.id
WHERE m.name = 'Montes'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_246'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_247', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_19' AND smd.res_id = s.id
WHERE m.name = 'Ribero'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_247'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_248', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_19' AND smd.res_id = s.id
WHERE m.name = 'Sucre'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_248'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_249', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_19' AND smd.res_id = s.id
WHERE m.name = 'Valdéz'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_249'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_250', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_20' AND smd.res_id = s.id
WHERE m.name = 'Andrés Bello'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_250'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_251', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_20' AND smd.res_id = s.id
WHERE m.name = 'Antonio Rómulo Costa'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_251'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_252', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_20' AND smd.res_id = s.id
WHERE m.name = 'Ayacucho'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_252'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_253', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_20' AND smd.res_id = s.id
WHERE m.name = 'Bolívar'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_253'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_254', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_20' AND smd.res_id = s.id
WHERE m.name = 'Cárdenas'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_254'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_255', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_20' AND smd.res_id = s.id
WHERE m.name = 'Córdoba'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_255'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_256', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_20' AND smd.res_id = s.id
WHERE m.name = 'Fernández Feo'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_256'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_257', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_20' AND smd.res_id = s.id
WHERE m.name = 'Francisco de Miranda'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_257'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_258', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_20' AND smd.res_id = s.id
WHERE m.name = 'García de Hevia'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_258'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_259', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_20' AND smd.res_id = s.id
WHERE m.name = 'Guásimos'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_259'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_260', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_20' AND smd.res_id = s.id
WHERE m.name = 'Independencia'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_260'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_261', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_20' AND smd.res_id = s.id
WHERE m.name = 'Jáuregui'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_261'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_262', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_20' AND smd.res_id = s.id
WHERE m.name = 'José María Vargas'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_262'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_263', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_20' AND smd.res_id = s.id
WHERE m.name = 'Junín'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_263'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_264', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_20' AND smd.res_id = s.id
WHERE m.name = 'Libertad'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_264'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_265', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_20' AND smd.res_id = s.id
WHERE m.name = 'Libertador'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_265'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_266', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_20' AND smd.res_id = s.id
WHERE m.name = 'Lobatera'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_266'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_267', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_20' AND smd.res_id = s.id
WHERE m.name = 'Michelena'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_267'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_268', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_20' AND smd.res_id = s.id
WHERE m.name = 'Panamericano'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_268'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_269', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_20' AND smd.res_id = s.id
WHERE m.name = 'Pedro María Ureña'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_269'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_270', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_20' AND smd.res_id = s.id
WHERE m.name = 'Rafael Urdaneta'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_270'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_271', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_20' AND smd.res_id = s.id
WHERE m.name = 'Samuel Darío Maldonado'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_271'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_272', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_20' AND smd.res_id = s.id
WHERE m.name = 'San Cristóbal'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_272'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_273', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_20' AND smd.res_id = s.id
WHERE m.name = 'Seboruco'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_273'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_274', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_20' AND smd.res_id = s.id
WHERE m.name = 'Simón Rodríguez'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_274'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_275', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_20' AND smd.res_id = s.id
WHERE m.name = 'Sucre'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_275'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_276', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_20' AND smd.res_id = s.id
WHERE m.name = 'Torbes'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_276'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_277', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_20' AND smd.res_id = s.id
WHERE m.name = 'Uribante'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_277'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_278', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_21' AND smd.res_id = s.id
WHERE m.name = 'Bocono'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_278'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_279', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_21' AND smd.res_id = s.id
WHERE m.name = 'Candelaria'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_279'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_280', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_21' AND smd.res_id = s.id
WHERE m.name = 'Carache'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_280'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_281', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_21' AND smd.res_id = s.id
WHERE m.name = 'Escuque'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_281'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_282', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_21' AND smd.res_id = s.id
WHERE m.name = 'Miranda'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_282'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_283', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_21' AND smd.res_id = s.id
WHERE m.name = 'Monte Carmelo'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_283'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_284', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_21' AND smd.res_id = s.id
WHERE m.name = 'Motatán'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_284'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_285', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_21' AND smd.res_id = s.id
WHERE m.name = 'Pam Pam'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_285'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_286', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_21' AND smd.res_id = s.id
WHERE m.name = 'Rafael Rangel'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_286'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_287', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_21' AND smd.res_id = s.id
WHERE m.name = 'San Rafael de Carvajal'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_287'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_288', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_21' AND smd.res_id = s.id
WHERE m.name = 'Sucre'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_288'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_289', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_21' AND smd.res_id = s.id
WHERE m.name = 'Trujillo'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_289'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_290', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_21' AND smd.res_id = s.id
WHERE m.name = 'Urdaneta'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_290'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_291', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_21' AND smd.res_id = s.id
WHERE m.name = 'Valera'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_291'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_292', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_21' AND smd.res_id = s.id
WHERE m.name = 'Andres Bello'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_292'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_293', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_21' AND smd.res_id = s.id
WHERE m.name = 'Bolivar'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_293'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_294', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_21' AND smd.res_id = s.id
WHERE m.name = 'Jose Felipe Marquez Cañizales'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_294'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_295', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_21' AND smd.res_id = s.id
WHERE m.name = 'Juan Vicente Campos Elías'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_295'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_296', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_21' AND smd.res_id = s.id
WHERE m.name = 'La Ceiba'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_296'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_297', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_21' AND smd.res_id = s.id
WHERE m.name = 'Pampanito'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_297'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_298', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_23' AND smd.res_id = s.id
WHERE m.name = 'Aristides Bastidas'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_298'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_299', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_23' AND smd.res_id = s.id
WHERE m.name = 'Bolivar'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_299'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_300', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_23' AND smd.res_id = s.id
WHERE m.name = 'Bruzal'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_300'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_301', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_23' AND smd.res_id = s.id
WHERE m.name = 'Cocorote'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_301'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_302', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_23' AND smd.res_id = s.id
WHERE m.name = 'Independencia'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_302'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_303', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_23' AND smd.res_id = s.id
WHERE m.name = 'Jose Antonio Paez'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_303'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_304', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_23' AND smd.res_id = s.id
WHERE m.name = 'La Trinidad'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_304'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_305', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_23' AND smd.res_id = s.id
WHERE m.name = 'Manuel Monge'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_305'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_306', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_23' AND smd.res_id = s.id
WHERE m.name = 'Nirgua'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_306'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_307', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_23' AND smd.res_id = s.id
WHERE m.name = 'Peña'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_307'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_308', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_23' AND smd.res_id = s.id
WHERE m.name = 'San Felipe'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_308'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_309', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_23' AND smd.res_id = s.id
WHERE m.name = 'Sucre'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_309'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_310', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_23' AND smd.res_id = s.id
WHERE m.name = 'Urachiche'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_310'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_311', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_23' AND smd.res_id = s.id
WHERE m.name = 'Veroes'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_311'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_312', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_24' AND smd.res_id = s.id
WHERE m.name = 'Almirante Padilla'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_312'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_313', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_24' AND smd.res_id = s.id
WHERE m.name = 'Baralt'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_313'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_314', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_24' AND smd.res_id = s.id
WHERE m.name = 'Cabimas'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_314'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_315', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_24' AND smd.res_id = s.id
WHERE m.name = 'Catatumbo'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_315'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_316', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_24' AND smd.res_id = s.id
WHERE m.name = 'Colón'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_316'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_317', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_24' AND smd.res_id = s.id
WHERE m.name = 'Jesus Enrique Lossada'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_317'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_318', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_24' AND smd.res_id = s.id
WHERE m.name = 'La Cañada de Urdaneta'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_318'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_319', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_24' AND smd.res_id = s.id
WHERE m.name = 'Lagunillas'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_319'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_320', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_24' AND smd.res_id = s.id
WHERE m.name = 'Machiques de Perijá'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_320'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_321', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_24' AND smd.res_id = s.id
WHERE m.name = 'Mara'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_321'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_322', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_24' AND smd.res_id = s.id
WHERE m.name = 'Maracaibo'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_322'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_323', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_24' AND smd.res_id = s.id
WHERE m.name = 'Miranda'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_323'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_324', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_24' AND smd.res_id = s.id
WHERE m.name = 'Paez'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_324'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_325', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_24' AND smd.res_id = s.id
WHERE m.name = 'Rosario de Perijá'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_325'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_326', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_24' AND smd.res_id = s.id
WHERE m.name = 'Santa Rita'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_326'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_327', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_24' AND smd.res_id = s.id
WHERE m.name = 'Sucre'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_327'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_328', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_24' AND smd.res_id = s.id
WHERE m.name = 'Valmore Rodríguez'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_328'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_329', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_24' AND smd.res_id = s.id
WHERE m.name = 'Francisco Javier Pulgar'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_329'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_330', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_24' AND smd.res_id = s.id
WHERE m.name = 'Jesus Maria Semprun'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_330'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_331', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_24' AND smd.res_id = s.id
WHERE m.name = 'San Francisco'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_331'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_332', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_24' AND smd.res_id = s.id
WHERE m.name = 'Simon Bolívar'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_332'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_333', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_22' AND smd.res_id = s.id
WHERE m.name = 'Vargas'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_333'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_municipality_334', 'res.country.municipality', m.id, true, now(), now(), 1, 1
FROM res_country_municipality m
JOIN res_country_municipality_res_country_state_rel rel ON rel.res_country_municipality_id = m.id
JOIN res_country_state s ON s.id = rel.res_country_state_id
JOIN ir_model_data smd ON smd.model='res.country.state' AND smd.module='binaural_location' AND smd.name='res_country_state_3' AND smd.res_id = s.id
WHERE m.name = 'Sotillo'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_municipality_334'
);
