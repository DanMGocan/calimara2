import React from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import { App } from "./App.jsx";
import { installPageZoom } from "./app/zoom.js";

// Before the first React render, so no content is laid out at the unscaled size first.
installPageZoom();

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
