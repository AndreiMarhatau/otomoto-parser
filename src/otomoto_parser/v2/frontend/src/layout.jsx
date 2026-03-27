import React from "react";
import { Link, NavLink } from "react-router-dom";
import {
  AppBar,
  Box,
  Breadcrumbs as MuiBreadcrumbs,
  Button,
  Chip,
  Container,
  IconButton as MuiIconButton,
  Link as MuiLink,
  Paper,
  Stack,
  Toolbar,
  Typography,
  alpha,
} from "@mui/material";

export function scrollWindowToPosition(top) {
  window.scrollTo(0, top);
  if (document.scrollingElement) document.scrollingElement.scrollTop = top;
  document.documentElement.scrollTop = top;
  document.body.scrollTop = top;
}

export function buildPageItems(currentPage, totalPages) {
  if (totalPages <= 7) return Array.from({ length: totalPages }, (_, index) => index + 1);
  const normalized = [...new Set([1, totalPages, currentPage - 1, currentPage, currentPage + 1])]
    .filter((page) => page >= 1 && page <= totalPages)
    .sort((a, b) => a - b);
  const items = [];
  for (const page of normalized) {
    const previous = items[items.length - 1];
    if (typeof previous === "number" && page - previous > 1) items.push("ellipsis");
    items.push(page);
  }
  return items;
}

export function IconButton({ title, onClick, href, disabled = false, tone = "default", children }) {
  const color = tone === "danger" ? "error" : tone === "secondary" ? "primary" : "default";
  if (href) {
    return (
      <MuiIconButton
        component="a"
        href={href}
        target="_blank"
        rel="noreferrer"
        color={color}
        title={title}
        aria-label={title}
      >
        {children}
      </MuiIconButton>
    );
  }
  return (
    <MuiIconButton type="button" color={color} title={title} aria-label={title} onClick={onClick} disabled={disabled}>
      {children}
    </MuiIconButton>
  );
}

export function Shell({ title, subtitle, actions = null, children, maxWidth = "xl" }) {
  return (
    <Box sx={{ pb: 8 }}>
      <AppBar
        position="sticky"
        color="transparent"
        elevation={0}
        sx={{
          borderBottom: 1,
          borderColor: "divider",
          backdropFilter: "blur(16px)",
          bgcolor: (theme) => alpha(theme.palette.background.default, 0.82),
        }}
      >
        <Container maxWidth="xl">
          <Toolbar disableGutters sx={{ minHeight: { xs: 74, md: 82 }, justifyContent: "space-between", gap: 2, py: 1 }}>
            <Stack component={Link} to="/" direction="row" spacing={1.5} alignItems="center" sx={{ textDecoration: "none", minWidth: 0 }}>
              <Paper
                elevation={0}
                sx={{ width: 42, height: 42, borderRadius: 3, display: "grid", placeItems: "center", bgcolor: "primary.main", color: "primary.contrastText", flexShrink: 0 }}
              >
                <Typography variant="subtitle2" fontWeight={800}>OP</Typography>
              </Paper>
              <Stack spacing={0.25} sx={{ minWidth: 0 }}>
                <Typography variant="subtitle1" fontWeight={700}>Otomoto Parser</Typography>
                <Typography variant="body2" color="text.secondary">Review workspace</Typography>
              </Stack>
            </Stack>
            <Stack component="nav" direction="row" spacing={1} aria-label="Primary" flexWrap="wrap" useFlexGap justifyContent="flex-end">
              <NavButton to="/" label="All requests" end />
              <NavButton to="/settings" label="Settings" />
            </Stack>
          </Toolbar>
        </Container>
      </AppBar>
      <Container maxWidth={maxWidth} sx={{ pt: { xs: 3, md: 5 } }}>
        <Stack spacing={3}>
          <Stack direction={{ xs: "column", md: "row" }} spacing={2.5} justifyContent="space-between" alignItems={{ xs: "flex-start", md: "flex-end" }}>
            <Box sx={{ maxWidth: 820 }}>
              <Typography variant="overline" color="text.secondary">Otomoto Parser</Typography>
              <Typography variant="h3" component="h1" sx={{ mt: 0.25 }}>{title}</Typography>
              {subtitle ? <Typography variant="body1" color="text.secondary" sx={{ mt: 1.25, maxWidth: 760 }}>{subtitle}</Typography> : null}
            </Box>
            {actions ? <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap justifyContent={{ xs: "flex-start", md: "flex-end" }}>{actions}</Stack> : null}
          </Stack>
          {children}
        </Stack>
      </Container>
    </Box>
  );
}

export function Breadcrumbs({ items }) {
  return (
    <MuiBreadcrumbs aria-label="Breadcrumbs">
      {items.map((item) =>
        item.to ? (
          <MuiLink component={Link} underline="hover" color="inherit" to={item.to} key={item.label}>
            {item.label}
          </MuiLink>
        ) : (
          <Typography color="text.secondary" key={item.label}>{item.label}</Typography>
        ),
      )}
    </MuiBreadcrumbs>
  );
}

export function StatusPill({ status }) {
  const color = status === "ready" ? "success" : status === "running" ? "warning" : status === "failed" ? "error" : "default";
  return <Chip size="small" color={color} label={status} sx={{ textTransform: "capitalize" }} />;
}

export function Metric({ label, value }) {
  return (
    <Paper variant="outlined" sx={{ px: 2, py: 1.5, minWidth: 140 }}>
      <Typography variant="body2" color="text.secondary">{label}</Typography>
      <Typography variant="subtitle1">{value ?? "—"}</Typography>
    </Paper>
  );
}

function NavButton({ to, label, end = false }) {
  return (
    <Button
      component={NavLink}
      to={to}
      end={end}
      color="inherit"
      variant="text"
      sx={{
        color: "text.secondary",
        px: 1.5,
        "&.active": { bgcolor: "action.selected", color: "text.primary" },
      }}
    >
      {label}
    </Button>
  );
}
