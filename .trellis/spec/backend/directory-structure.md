# Backend structure

`ingest.py` owns CSV/JSON/XLSX and original evidence. `normalization.py` owns strict
numeric/tax/fee interpretation. `engine.py` owns scoped comparisons, references,
human replay and decision gates. `scoring.py` owns ratio scoring. `service.py` is
the shared application entry. `reports.py` projects results; `cli.py` and `app.py`
expose local interfaces. `templates.py` contains synthetic example factories.

Example: `run_comparison(paths, as_of="2026-11-02")` reads records, invokes the
engine and builds advice. Neither interface implements its own business scoring.
