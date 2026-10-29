import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import "./index.css";
import Layout from "./components/Layout";
import { HealthProvider } from "./hooks/useHealth";
import About from "./pages/About";
import Analyze from "./pages/Analyze";
import ApiDocs from "./pages/ApiDocs";
import Batch from "./pages/Batch";
import History from "./pages/History";
import Home from "./pages/Home";
import NotFound from "./pages/NotFound";
import Report from "./pages/Report";
import Status from "./pages/Status";

const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: "/", element: <Home /> },
      { path: "/analyze", element: <Analyze /> },
      { path: "/batch", element: <Batch /> },
      { path: "/history", element: <History /> },
      { path: "/report/:id", element: <Report /> },
      { path: "/status", element: <Status /> },
      { path: "/docs", element: <ApiDocs /> },
      { path: "/about", element: <About /> },
      { path: "*", element: <NotFound /> },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <HealthProvider>
      <RouterProvider router={router} />
    </HealthProvider>
  </StrictMode>,
);
