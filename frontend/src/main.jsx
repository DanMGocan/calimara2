import React from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import { App } from "./App.jsx";
import { installPageZoom } from "./app/zoom.js";

// Before the first render, so the page never paints at the wrong scale.
installPageZoom();

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
