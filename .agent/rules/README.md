# AI Agent Rules

This directory contains the canonical rules for AI development agents working on TeleCLI.

## Structure

- **`base.md`** - The single source of truth for all AI agent development rules
- **`gemini.md`** - Symlink to `base.md` (for Antigravity/Gemini compatibility)

## Tool-Specific Rules

The following files in the repository root are symlinks to `.agent/rules/base.md`:

- **`.geminirules`** - Used by Antigravity/Gemini AI agents
- **`.cursorrules`** - Used by Cursor IDE's AI assistant

## Why Symlinks?

Using symlinks ensures:
1. **Single Source of Truth**: All rules are maintained in one place (`base.md`)
2. **Automatic Synchronization**: Updates to `base.md` are immediately reflected in all tool-specific files
3. **No Duplication**: Eliminates the risk of rules diverging over time
4. **Tool Compatibility**: Each tool can still find its expected configuration file

## Making Changes

To update the AI agent rules:
1. Edit **only** `.agent/rules/base.md`
2. All symlinked files will automatically reflect the changes
3. No need to update multiple files manually

## Git Note

Symlinks are tracked in Git, so they work seamlessly across different machines and in CI/CD environments.
