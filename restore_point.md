# Restore Point

- **Commit Hash**: `1bfce7fa8baab618650dfff72180effc1b05431c`
- **Tag**: `restore-before-results-move`
- **Date**: `2026-11-17`

## How to Restore

To inspect the repo at this point without modifying current branch state:
```bash
git checkout restore-before-results-move
```

To completely undo all changes made after this point and restore working directory:
```bash
git reset --hard restore-before-results-move
```

To restore a specific file to its state at this restore point:
```bash
git checkout restore-before-results-move -- <path>
```
