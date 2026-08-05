Employees and payroll plugin raw files for SPRK.

The plugin currently ships three company-scoped extensions:

- `employees-page`: employee records plus employee-level payroll rates, tax defaults, and benefit defaults.
- `payroll-settings-page`: global payroll defaults and GL account mapping.
- `payroll-runs-page`: grid-oriented payroll run data entry, plugin-owned calculations, pay stub render metadata, and confirm-time journal posting.

Zip the contents of this folder, not the parent directory, so the archive root contains `manifest.json` and `extensions/`.

Example:

```bash
cd /Users/nathancunningham/Code/SPRK_Plugins/employees
zip -r ../employees.zip manifest.json extensions
```
