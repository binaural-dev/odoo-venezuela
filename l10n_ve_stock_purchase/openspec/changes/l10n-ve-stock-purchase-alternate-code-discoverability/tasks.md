## 1. Manifest and README

- [x] 1.1 Update `summary` and `description` in `__manifest__.py` to mention Código Alterno search/column. Verified by `python3 -c "import ast; ast.parse(open('__manifest__.py').read())"`.
- [x] 1.2 Bump the manifest `version` from `19.0.1.2.0` to `19.0.1.2.1` (docs-only patch bump).
- [x] 1.3 Update the `l10n_ve_stock_purchase` entry in the repo-root `README.md` to mention Código Alterno.

## 2. Verification

- [ ] 2.1 Confirm the manifest `summary`/`description` render correctly in Apps (Settings > Apps > search "código alterno" finds the module).
