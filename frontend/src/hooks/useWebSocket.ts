"use client";
import { useEffect, useCallback } from "react";
import { getWSClient } from "@/lib/websocket";
import { WSMessage } from "@/types";

export function useWebSocket(handler: (msg: WSMessage) => void) {
  const stableHandler = useCallback(handler, []);
  useEffect(() => {
    const client = getWSClient();
    const unsub = client.subscribe(stableHandler);
    return unsub;
  }, [stableHandler]);
}
