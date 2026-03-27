import React from "react";
import {
  CssBaseline,
  GlobalStyles,
  ThemeProvider,
  alpha,
  createTheme,
  responsiveFontSizes,
  useMediaQuery,
} from "@mui/material";

export const themeTokens = {
  light: {
    palette: {
      primary: "#0f766e",
      secondary: "#b7791f",
      error: "#c24141",
      warning: "#c47f17",
      success: "#24805f",
      backgroundDefault: "#eef3f4",
      backgroundPaper: "#fbfcfc",
      textPrimary: "#1f2d2d",
      textSecondary: "#5c6f71",
      divider: "rgba(48, 71, 71, 0.12)",
    },
    gradients: {
      body: "radial-gradient(circle at top, rgba(15,118,110,0.09), transparent 24%)",
    },
    surfaces: {
      field: "rgba(255, 255, 255, 0.84)",
    },
  },
  dark: {
    palette: {
      primary: "#7dd3c7",
      secondary: "#f3c677",
      error: "#f6a5a5",
      warning: "#f3c677",
      success: "#7ed6a7",
      backgroundDefault: "#0f1720",
      backgroundPaper: "#16212c",
      textPrimary: "#edf4f4",
      textSecondary: "#a6b7b7",
      divider: "rgba(173, 196, 196, 0.18)",
    },
    gradients: {
      body: "radial-gradient(circle at top, rgba(125,211,199,0.12), transparent 28%)",
    },
    surfaces: {
      field: "rgba(255, 255, 255, 0.02)",
    },
  },
};

export function buildTheme(mode) {
  const tokens = themeTokens[mode];
  const theme = createTheme({
    palette: {
      mode,
      primary: { main: tokens.palette.primary },
      secondary: { main: tokens.palette.secondary },
      error: { main: tokens.palette.error },
      warning: { main: tokens.palette.warning },
      success: { main: tokens.palette.success },
      background: {
        default: tokens.palette.backgroundDefault,
        paper: tokens.palette.backgroundPaper,
      },
      text: {
        primary: tokens.palette.textPrimary,
        secondary: tokens.palette.textSecondary,
      },
      divider: tokens.palette.divider,
    },
    shape: { borderRadius: 20 },
    typography: {
      fontFamily: '"Instrument Sans", "Avenir Next", "Segoe UI", sans-serif',
      h1: { fontWeight: 700, letterSpacing: "-0.03em" },
      h2: { fontWeight: 700, letterSpacing: "-0.03em" },
      h3: { fontWeight: 700, letterSpacing: "-0.02em" },
      button: { fontWeight: 600, textTransform: "none" },
    },
    components: {
      MuiButtonBase: { defaultProps: { disableRipple: false } },
      MuiButton: {
        styleOverrides: {
          root: ({ theme: currentTheme }) => ({
            borderRadius: 999,
            boxShadow: "none",
            paddingInline: currentTheme.spacing(2),
          }),
        },
      },
      MuiChip: {
        styleOverrides: {
          root: ({ theme: currentTheme }) => ({
            borderRadius: 999,
            fontWeight: 600,
            backgroundColor: alpha(currentTheme.palette.primary.main, 0.08),
          }),
        },
      },
      MuiCard: {
        styleOverrides: {
          root: ({ theme: currentTheme }) => ({
            borderRadius: 24,
            boxShadow: "none",
            border: `1px solid ${currentTheme.palette.divider}`,
            backgroundImage: "none",
          }),
        },
      },
      MuiPaper: {
        styleOverrides: {
          root: { backgroundImage: "none" },
        },
      },
      MuiOutlinedInput: {
        styleOverrides: {
          root: {
            borderRadius: 18,
            backgroundColor: tokens.surfaces.field,
          },
        },
      },
      MuiDialog: {
        styleOverrides: {
          paper: ({ theme: currentTheme }) => ({
            borderRadius: 28,
            border: `1px solid ${currentTheme.palette.divider}`,
          }),
        },
      },
      MuiAccordion: {
        styleOverrides: {
          root: ({ theme: currentTheme }) => ({
            borderRadius: 18,
            border: `1px solid ${currentTheme.palette.divider}`,
            boxShadow: "none",
            "&::before": { display: "none" },
            "& + &": { marginTop: currentTheme.spacing(1) },
          }),
        },
      },
    },
    customTokens: tokens,
  });

  return responsiveFontSizes(theme, { factor: 2.2 });
}

export function AppThemeProvider({ children }) {
  const prefersDarkMode = useMediaQuery("(prefers-color-scheme: dark)");
  const theme = React.useMemo(() => buildTheme(prefersDarkMode ? "dark" : "light"), [prefersDarkMode]);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline enableColorScheme />
      <GlobalStyles
        styles={{
          ":root": { colorScheme: theme.palette.mode },
          "*, *::before, *::after": { boxSizing: "border-box" },
          "html, body, #root": { minHeight: "100%" },
          body: {
            margin: 0,
            backgroundImage:
              theme.customTokens.gradients.body,
            backgroundColor: theme.palette.background.default,
            color: theme.palette.text.primary,
            overflowX: "hidden",
          },
          a: { color: "inherit" },
        }}
      />
      {children}
    </ThemeProvider>
  );
}
