# Project Status - Phase 28 Baseline

## Current baseline

- The project runs locally.
- Local database can be reset safely.
- Test files are intentionally removed.
- Phase-based test files are removed.
- Python cache files are ignored/removed.
- .env and sqlite database files are ignored.
- reference_old is kept only as archive/reference.
- current_project is the active Django project.

## Current route policy

- Platform owner: /loginlogin/
- Company admin/operator: /<companyCode>/admin/
- Technician: /<companyCode>/tech/
- Public/customer: /<companyCode>/

## Known decision

Tests are not part of this local project anymore. Use smoke-check commands instead.
