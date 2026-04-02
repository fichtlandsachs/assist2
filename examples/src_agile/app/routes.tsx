import { createBrowserRouter } from "react-router";
import { Layout } from "./components/Layout";
import { Dashboard } from "./components/Dashboard";
import { KarlAssistant } from "./components/KarlAssistant";
import { Board } from "./components/Board";
import { Retrospective } from "./components/Retrospective";
import { Team, Planning } from "./components/ComingSoon";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: Layout,
    children: [
      { index: true, Component: Dashboard },
      { path: "chat", Component: KarlAssistant },
      { path: "board", Component: Board },
      { path: "retro", Component: Retrospective },
      { path: "team", Component: Team },
      { path: "planning", Component: Planning },
      { path: "*", Component: Dashboard },
    ],
  },
]);
