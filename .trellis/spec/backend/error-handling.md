# Error handling

Input parsing and business configuration errors raise actionable `ValueError`.
Business uncertainty produces structured issues with code, field, severity,
message and supplier question; it never silently becomes a zero or a safe result.
CLI returns exit2 for expected input/filesystem errors. UI displays failed runs
without inventing successful results. Original files are preserved on all failures.
