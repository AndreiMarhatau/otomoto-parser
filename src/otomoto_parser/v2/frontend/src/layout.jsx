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

export function Shell({ title, subtitle, actions = null, children }) {
  return (
    <Box sx={{ pb: 6 }}>
      <AppBar position="static" color="transparent" elevation={0} sx={{ borderBottom: 1, borderColor: "divider", backdropFilter: "blur(12px)" }}>
        <Container maxWidth="xl">
          <Toolbar disableGutters sx={{ minHeight: 72, justifyContent: "space-between", gap: 2 }}>
            <Stack component={Link} to="/" direction="row" spacing={1.5} alignItems="center" sx={{ textDecoration: "none" }}>
              <Paper
                elevation={0}
                sx={{ width: 40, height: 40, borderRadius: 3, display: "grid", placeItems: "center", bgcolor: "primary.main", color: "primary.contrastText" }}
              >
                <Typography variant="subtitle2" fontWeight={800}>OP</Typography>
              </Paper>
              <Stack spacing={0.25}>
                <Typography variant="subtitle1" fontWeight={700}>Otomoto Parser</Typography>
                <Typography variant="body2" color="text.secondary">Review workspace</Typography>
              </Stack>
            </Stack>
            <Stack component="nav" direction="row" spacing={1} aria-label="Primary">
              <NavButton to="/" label="All requests" end />
              <NavButton to="/settings" label="Settings" />
            </Stack>
          </Toolbar>
        </Container>
      </AppBar>
      <Container maxWidth="xl" sx={{ pt: { xs: 3, md: 4 } }}>
        <Stack spacing={3}>
          <Stack direction={{ xs: "column", md: "row" }} spacing={2} justifyContent="space-between" alignItems={{ xs: "flex-start", md: "center" }}>
            <Box>
              <Typography variant="overline" color="text.secondary">Otomoto Parser</Typography>
              <Typography variant="h4" component="h1">{title}</Typography>
              {subtitle ? <Typography variant="body1" color="text.secondary" sx={{ mt: 1, maxWidth: 760 }}>{subtitle}</Typography> : null}
            </Box>
            {actions ? <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>{actions}</Stack> : null}
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
        "&.active": { bgcolor: "action.selected", color: "text.primary" },
      }}
    >
      {label}
    </Button>
  );
}
