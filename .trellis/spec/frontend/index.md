# Local review interface conventions

The interface is a single-user, localhost-only Streamlit app. It invokes the shared
service and renders projections from `reports.py`; it never recalculates decisions.
Supplier strings are data, never interpolated into raw HTML or unescaped Markdown.
Evidence tables retain exact raw values; heterogeneous UI columns become display
strings. Session files use isolated date-scoped temporary directories. Operators
download the complete result/review files for permanent evidence retention.

Check UI behavior with Streamlit AppTest and actual localhost startup. Preserve the
light visual design, Microsoft YaHei preference and no fill colors in Excel tables.
