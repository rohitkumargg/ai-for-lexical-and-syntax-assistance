# Restore Point

- **Commit Hash**: `35b16b7ed638a09c2bf50ffbed73b4d22ddc2f36` (`35b16b7`)
- **Tag**: `restore-before-sim-fix`
- **Date**: `2026-11-17`

## How to Restore

To look / inspect the repository at this restore point:
```bash
git checkout restore-before-sim-fix
```

To undo everything after it and reset the working directory:
```bash
git reset --hard restore-before-sim-fix
```

To restore one file:
```bash
git checkout restore-before-sim-fix -- <path>
```
