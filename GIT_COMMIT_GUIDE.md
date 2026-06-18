# Git Commit History Guide

## Overview

This project maintains detailed commit descriptions in two places:

1. **CHANGELOG.md** - High-level project history with feature descriptions
2. **Git Notes** - Detailed descriptions attached to each commit (non-destructive, doesn't change commit hash)

## Why Two Methods?

- **CHANGELOG.md**: Easy to read, search, and provides comprehensive feature context
- **Git Notes**: Attached to commits, visible when examining git history, non-invasive way to improve commit messages

## How to View

### View CHANGELOG
Simply open [CHANGELOG.md](./CHANGELOG.md)

### View Git Notes with Commits

#### Method 1: Full Detail View
```bash
git log --notes --pretty=fuller
```

This shows each commit with full details including the attached notes.

#### Method 2: Custom Format (More Readable)
```bash
git log --notes -8 --format="%h %s%n  Notes: %N%n"
```

#### Method 3: Configure Default Display
```bash
git config --local format.notes true
git log
```

This makes notes appear by default in all log output.

#### Method 4: View Notes for Specific Commit
```bash
git notes show <commit-hash>
```

For example:
```bash
git notes show aa4fc93
```

### Compare Commit Message vs Notes

Original commit messages use action-based language (add/remove/refactor).

Enhanced descriptions in notes focus on **functionality and impact**:

| Commit | Original | Enhanced Note |
|--------|----------|---------------|
| `aa4fc93` | "Remove 4 monitoring Python files" | "Streamline project by removing deprecated monitoring utilities" |
| `cb8f43f` | "refactor: reorganize..." | "Restructure project into modular components: LUT tables, monitoring tools, RTL modules, and data management" |
| `d186aeb` | "feat: add FPGA RTL..." | "Integrate complete RTL design: channel simulator, metrics counter, and key evaluator" |
| `fb9b98c` | "feat: add FPGA quantum..." | "Implement quantum key extraction and sifting mechanisms with performance metrics" |

## Viewing in Different Git Tools

### GitHub.com
GitHub displays git notes in the commit view. Look for the "Notes" section below commit details.

### VS Code
Right-click a commit in the timeline → View Details (shows notes if configured).

### GitLens Extension
Install GitLens for VS Code to see notes integrated into the commit history view.

### Command Line
```bash
# Clone with notes support
git clone --recursive <repo-url>
git fetch origin refs/notes/commits:refs/notes/commits

# Or if already cloned, fetch notes
git fetch origin refs/notes/commits:refs/notes/commits
```

## Project Development Phases

Based on CHANGELOG.md, the project evolved through these phases:

1. **Foundation** (c9982e7): Base TRNG and IIR filtering
2. **Restructuring** (cb8f43f): Organized into modular architecture
3. **RTL Development** (d186aeb): Complete FPGA design implementation
4. **Feature Enhancement** (bebbc52-fb9b98c): Visualization, bitstream capture, key extraction
5. **Optimization** (aa4fc93): Streamlined deprecated components

## Best Practices

When reviewing this project:
- Check CHANGELOG.md for feature overview
- Use `git log --notes` to understand WHY changes were made
- Read commit descriptions in notes for technical context
- Reference individual files for implementation details

## Adding New Git Notes

To add notes to future commits:
```bash
git notes add -m "Your note here" <commit-hash>
git push origin refs/notes/commits
```

## Future Commits

Follow these guidelines for new commits:

**Original Message** (concise, action-based):
```
feat: add real-time channel monitoring
```

**Git Note** (functional description):
```
git notes add -m "Implement live channel parameter tracking with adaptive threshold adjustment based on QBER fluctuations"
```

This provides clarity without polluting the main commit message.
 