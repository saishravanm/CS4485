import { createRoot } from "react-dom/client";
import { RecoilRoot } from "recoil";
import { ChainlitAPI, ChainlitContext } from "@chainlit/react-client";
import App from "./App";
import "./index.css";

const CHAINLIT_SERVER_URL = import.meta.env.VITE_CHAINLIT_URL ?? "http://localhost:8000";
const apiClient = new ChainlitAPI(CHAINLIT_SERVER_URL, "webapp");

createRoot(document.getElementById("root")!).render(
  <ChainlitContext.Provider value={apiClient}>
    <RecoilRoot>
      <App />
    </RecoilRoot>
  </ChainlitContext.Provider>
);
