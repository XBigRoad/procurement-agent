# Types

Python dataclasses describe Upload and ReviewSession. Shared service dictionaries
follow `docs/DATA_CONTRACT.md`. Validate JSON objects and expected business fields
at boundaries. Heterogeneous display columns are converted explicitly to strings;
uniform numeric columns keep numeric types for useful sorting.
