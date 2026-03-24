import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import "./styles.css";
import { api } from "./api";
import { RequestDetailPage } from "./request-detail-page";
import { RequestListPage } from "./request-list-page";
import { RequestResultsPage } from "./request-results-page";
import { SettingsPage } from "./settings-page";
import { usePolling } from "./use-polling";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<RequestListPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/requests/:requestId" element={<RequestDetailPage />} />
        <Route path="/requests/:requestId/results" element={<RequestResultsPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export { App, RequestDetailPage, RequestResultsPage, SettingsPage, api, usePolling };

const rootElement = document.getElementById("root");
if (rootElement) {
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
}
