"use client";

import { motion } from "framer-motion";
import { CheckCircle2, AlertTriangle } from "lucide-react";

export function ValueSection() {
  return (
    <section className="py-24 bg-[#FAFAFA] border-y border-gray-200">
      <div className="max-w-7xl mx-auto px-6 md:px-12">
        <div className="text-center mb-16 max-w-3xl mx-auto">
          <motion.h2 
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: false, margin: "-40px" }}
            transition={{ duration: 0.5 }}
            className="text-3xl md:text-4xl lg:text-5xl font-bold tracking-tight text-gray-900 mb-6"
          >
            Don't just detect the failure. <br className="hidden md:block" /> Understand it.
          </motion.h2>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: false, margin: "-40px" }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="text-lg text-gray-600"
          >
            Traditional monitoring tells you that something is broken. FixFlow tells you exactly what changed, why it broke, what else is affected, and how to safely repair it.
          </motion.p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-12 gap-8 max-w-[1200px] mx-auto">
          
          {/* Statistic Card */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: false, margin: "-40px" }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="md:col-span-5 bg-white border border-gray-200 rounded-3xl p-10 flex flex-col justify-center items-center text-center shadow-sm relative overflow-hidden"
          >
            {/* Subtle glow */}
            <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-100/50 blur-[80px] rounded-full" />
            
            <div className="text-[120px] font-bold text-gray-900 leading-none tracking-tighter mb-4 relative z-10">
              99<span className="text-5xl text-indigo-600">%</span>
            </div>
            <h3 className="text-xl font-semibold text-gray-900 mb-2 relative z-10">Faster Incident Recovery</h3>
            <p className="text-gray-500 relative z-10">
              Teams using FixFlow spend almost zero time manually hunting for root causes in logs.
            </p>
          </motion.div>

          {/* Features List */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: false, margin: "-40px" }}
            transition={{ duration: 0.5, delay: 0.3 }}
            className="md:col-span-7 bg-[#111] border border-gray-800 rounded-3xl p-10 shadow-xl relative overflow-hidden flex flex-col justify-center"
          >
            {/* Subtle glow */}
            <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-900/20 blur-[80px] rounded-full" />
            
            <h3 className="text-2xl font-semibold text-white mb-8 relative z-10">With FixFlow</h3>
            
            <ul className="space-y-6 relative z-10">
              {[
                { label: "Detect", desc: "abnormal behavior automatically without manual alert configuration." },
                { label: "Correlate", desc: "logs, code changes, and architecture in real-time." },
                { label: "Reason", desc: "the exact root cause of the failure down to the commit." },
                { label: "Repair", desc: "with an AI-generated multi-file patch." },
                { label: "Verify", desc: "through a strict, automated safety pipeline." }
              ].map((item, i) => (
                <li key={i} className="flex items-start gap-4">
                  <div className="mt-1 w-6 h-6 rounded-full bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center shrink-0">
                    <CheckCircle2 className="w-3.5 h-3.5 text-indigo-400" />
                  </div>
                  <div>
                    <span className="text-white font-medium text-lg">{item.label}</span>
                    <span className="text-gray-400 block mt-0.5">{item.desc}</span>
                  </div>
                </li>
              ))}
            </ul>
          </motion.div>

        </div>
      </div>
    </section>
  );
}


