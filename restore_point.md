# Restore Point

- **Commit Hash**: `2bc6f95d60ed70c7fb1599b41d34b50d05793793`
- **Tag**: `restore-before-attack-defences`
- **Date**: `2026-11-17`

## How to Restore

To inspect the repo at this point without modifying current branch state:
```bash
git checkout restore-before-attack-defences
```

To completely undo all changes made after this point and restore working directory:
```bash
git reset --hard restore-before-attack-defences
```

To restore a specific file to its state at this restore point:
```bash
git checkout restore-before-attack-defences -- <path>
```
