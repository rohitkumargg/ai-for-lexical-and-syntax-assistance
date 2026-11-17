# Restore Point

- **Commit Hash**: `17b246759995e733341212f3a3e95f277c228934` (`17b2467`)
- **Tag**: `restore-before-electron`
- **Date**: `2026-11-17`

## How to Restore

To look / inspect the repository at this restore point:
```bash
git checkout restore-before-electron
```

To undo everything after it and reset the working directory:
```bash
git reset --hard restore-before-electron
```

To restore one file:
```bash
git checkout restore-before-electron -- <path>
```
