import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "./api";

interface Ctx {
  live: boolean;
  modelLoaded: boolean;
  device: string;
  recordsCount: number;
  modelError: string | null;
  checking: boolean;
  refreshHealth: () => void;
}

const ApiCtx = createContext<Ctx>({
  live: false,
  modelLoaded: false,
  device: "",
  recordsCount: 0,
  modelError: null,
  checking: true,
  refreshHealth: () => {},
});

export const useApi = () => useContext(ApiCtx);

export function ApiProvider({ children }: { children: ReactNode }) {
  const [s, setS] = useState<Omit<Ctx, "refreshHealth">>({
    live: false,
    modelLoaded: false,
    device: "",
    recordsCount: 0,
    modelError: null,
    checking: true,
  });

  const check = useCallback(() => {
    api.health()
      .then((h) =>
        setS({
          live: true,
          modelLoaded: Boolean(h.model_loaded),
          device: h.device ?? "",
          recordsCount: h.records ?? 0,
          modelError: (h as { model_error?: string | null }).model_error ?? null,
          checking: false,
        })
      )
      .catch(() =>
        setS({
          live: false,
          modelLoaded: false,
          device: "",
          recordsCount: 0,
          modelError: null,
          checking: false,
        })
      );
  }, []);

  useEffect(() => {
    check();
    const t = setInterval(check, 15000);
    return () => clearInterval(t);
  }, [check]);

  return <ApiCtx.Provider value={{ ...s, refreshHealth: check }}>{children}</ApiCtx.Provider>;
}
