"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";

export function AnnouncementBar() {
  return (
    <div className="bg-[#111111] text-white py-2.5 px-4 text-center text-xs sm:text-sm font-medium tracking-wide">
      <Link href="/dashboard" className="inline-flex items-center gap-2 hover:text-[#E9D5FF] transition-colors group">
        <span>Continuous monitoring. Root-cause intelligence. Verified recovery.</span>
        <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
      </Link>
    </div>
  );
}


