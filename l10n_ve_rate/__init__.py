from . import models

import logging

_logger = logging.getLogger(__name__)

old_module = "binaural_rate"
new_module = "l10n_ve_rate"


def pre_init_hook(env):
	"""Reassign ir.model.data entries from binaural_rate to l10n_ve_rate.

	Tolerates being called with either an Environment-like object (with .cr)
	or a bare cursor. Updates ir_model_data.module so existing data bindings
	remain valid under the new module namespace.
	"""
	cr = getattr(env, "cr", env)
	try:
		_logger.info(
			"Running pre_init_hook for l10n_ve_rate: reassigning data from %s to %s",
			old_module,
			new_module,
		)
		reassign_rate_data_ids(cr)
	except Exception as e:
		_logger.exception("Error running pre_init_hook for l10n_ve_rate: %s", e)


def reassign_rate_data_ids(cr):
	execute_script_sql_all(cr)


def execute_script_sql_all(cr):
	try:
		cr.execute("SELECT count(*) FROM ir_model_data WHERE module = %s", (old_module,))
		before_cnt = cr.fetchone()[0]
		_logger.info("ir_model_data rows with module '%s' before update: %s", old_module, before_cnt)

		cr.execute(
			"""
			UPDATE ir_model_data
			SET module=%s
			WHERE module=%s
			""",
			(new_module, old_module),
		)

		cr.execute("SELECT count(*) FROM ir_model_data WHERE module = %s", (new_module,))
		after_cnt = cr.fetchone()[0]
		_logger.info(
			"Updated ir_model_data.module rows: before=%s, after=%s", before_cnt, after_cnt
		)
	except Exception:
		_logger.exception("Failed to update ir_model_data.module from %s to %s", old_module, new_module)


def execute_script_sql(cr, xml_id_prefix):
	"""Optionally update only rows whose name starts with the given prefix."""
	try:
		cr.execute(
			"SELECT count(*) FROM ir_model_data WHERE module = %s AND name LIKE %s",
			(old_module, f"{xml_id_prefix}%"),
		)
		before = cr.fetchone()[0]
		_logger.info("ir_model_data rows with prefix '%s' before update: %s", xml_id_prefix, before)

		cr.execute(
			"""
			UPDATE ir_model_data
			SET module=%s
			WHERE module=%s AND name LIKE %s
			""",
			(new_module, old_module, f"{xml_id_prefix}%"),
		)

		cr.execute(
			"SELECT count(*) FROM ir_model_data WHERE module = %s AND name LIKE %s",
			(new_module, f"{xml_id_prefix}%"),
		)
		after = cr.fetchone()[0]
		_logger.info(
			"Updated ir_model_data.module rows with prefix %s: before=%s, after=%s",
			xml_id_prefix,
			before,
			after,
		)
	except Exception:
		_logger.exception(
			"Failed to update ir_model_data.module rows with prefix %s from %s to %s",
			xml_id_prefix,
			old_module,
			new_module,
		)
