"use client";

import { useEffect } from "react";
import { DEMO_MODE, DEMO_TOKEN } from "@/lib/demo-data";

export default function DemoTokenInjector() {
  useEffect(() => {
    // In demo mode, auto-inject the token so API client recognises demo mode
    if (DEMO_MODE) {
      localStorage.setItem("patchr_token", DEMO_TOKEN);
    }
  }, []);
  return null;
}
