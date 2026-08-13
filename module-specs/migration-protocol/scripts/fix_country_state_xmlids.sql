-- 25 registros a verificar/reparar

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_state_1', 'res.country.state', s.id, true, now(), now(), 1, 1
FROM res_country_state s
WHERE s.country_id = 238 AND s.code = 'DC'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_state_1'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_state_2', 'res.country.state', s.id, true, now(), now(), 1, 1
FROM res_country_state s
WHERE s.country_id = 238 AND s.code = 'AM'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_state_2'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_state_3', 'res.country.state', s.id, true, now(), now(), 1, 1
FROM res_country_state s
WHERE s.country_id = 238 AND s.code = 'AZ'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_state_3'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_state_4', 'res.country.state', s.id, true, now(), now(), 1, 1
FROM res_country_state s
WHERE s.country_id = 238 AND s.code = 'AP'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_state_4'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_state_5', 'res.country.state', s.id, true, now(), now(), 1, 1
FROM res_country_state s
WHERE s.country_id = 238 AND s.code = 'AR'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_state_5'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_state_6', 'res.country.state', s.id, true, now(), now(), 1, 1
FROM res_country_state s
WHERE s.country_id = 238 AND s.code = 'BA'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_state_6'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_state_7', 'res.country.state', s.id, true, now(), now(), 1, 1
FROM res_country_state s
WHERE s.country_id = 238 AND s.code = 'BO'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_state_7'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_state_8', 'res.country.state', s.id, true, now(), now(), 1, 1
FROM res_country_state s
WHERE s.country_id = 238 AND s.code = 'CB'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_state_8'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_state_9', 'res.country.state', s.id, true, now(), now(), 1, 1
FROM res_country_state s
WHERE s.country_id = 238 AND s.code = 'CJ'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_state_9'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_state_10', 'res.country.state', s.id, true, now(), now(), 1, 1
FROM res_country_state s
WHERE s.country_id = 238 AND s.code = 'DA'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_state_10'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_state_11', 'res.country.state', s.id, true, now(), now(), 1, 1
FROM res_country_state s
WHERE s.country_id = 238 AND s.code = 'FC'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_state_11'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_state_12', 'res.country.state', s.id, true, now(), now(), 1, 1
FROM res_country_state s
WHERE s.country_id = 238 AND s.code = 'GR'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_state_12'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_state_13', 'res.country.state', s.id, true, now(), now(), 1, 1
FROM res_country_state s
WHERE s.country_id = 238 AND s.code = 'LR'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_state_13'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_state_14', 'res.country.state', s.id, true, now(), now(), 1, 1
FROM res_country_state s
WHERE s.country_id = 238 AND s.code = 'MD'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_state_14'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_state_15', 'res.country.state', s.id, true, now(), now(), 1, 1
FROM res_country_state s
WHERE s.country_id = 238 AND s.code = 'MR'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_state_15'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_state_16', 'res.country.state', s.id, true, now(), now(), 1, 1
FROM res_country_state s
WHERE s.country_id = 238 AND s.code = 'MN'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_state_16'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_state_17', 'res.country.state', s.id, true, now(), now(), 1, 1
FROM res_country_state s
WHERE s.country_id = 238 AND s.code = 'NE'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_state_17'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_state_18', 'res.country.state', s.id, true, now(), now(), 1, 1
FROM res_country_state s
WHERE s.country_id = 238 AND s.code = 'PT'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_state_18'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_state_19', 'res.country.state', s.id, true, now(), now(), 1, 1
FROM res_country_state s
WHERE s.country_id = 238 AND s.code = 'SC'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_state_19'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_state_20', 'res.country.state', s.id, true, now(), now(), 1, 1
FROM res_country_state s
WHERE s.country_id = 238 AND s.code = 'TC'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_state_20'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_state_21', 'res.country.state', s.id, true, now(), now(), 1, 1
FROM res_country_state s
WHERE s.country_id = 238 AND s.code = 'TR'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_state_21'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_state_22', 'res.country.state', s.id, true, now(), now(), 1, 1
FROM res_country_state s
WHERE s.country_id = 238 AND s.code = 'VA'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_state_22'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_state_23', 'res.country.state', s.id, true, now(), now(), 1, 1
FROM res_country_state s
WHERE s.country_id = 238 AND s.code = 'YC'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_state_23'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_state_24', 'res.country.state', s.id, true, now(), now(), 1, 1
FROM res_country_state s
WHERE s.country_id = 238 AND s.code = 'ZU'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_state_24'
);

INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date, create_uid, write_uid)
SELECT 'binaural_location', 'res_country_state_25', 'res.country.state', s.id, true, now(), now(), 1, 1
FROM res_country_state s
WHERE s.country_id = 238 AND s.code = 'DF'
AND NOT EXISTS (
    SELECT 1 FROM ir_model_data WHERE module='binaural_location' AND name='res_country_state_25'
);
