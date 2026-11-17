# Restore Point

- **Commit Hash**: `08cb3deccbde5793cba2441341add5f275a377e0` (`08cb3de`)
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
