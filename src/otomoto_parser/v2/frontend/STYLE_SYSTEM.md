Frontend styling is MUI-first.

- `src/app-theme.jsx` is the single source of truth for theme semantics, tokens, component overrides, and global page styles.
- New styling work should use MUI theme tokens, component variants, `sx`, or `GlobalStyles` from that file.
- Do not reintroduce parallel CSS token files or page-level legacy stylesheets unless there is a concrete non-MUI requirement.
