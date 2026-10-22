import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { ApiProvider } from "./context";
import { ErrorBoundary } from "./components/ErrorBoundary";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <ApiProvider>
          <App />
        </ApiProvider>
      </BrowserRouter>
    </ErrorBoundary>
  </React.StrictMode>,
);
