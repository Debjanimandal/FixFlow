"use client";

import { motion } from "framer-motion";
import { Lock, FileText, Server, History } from "lucide-react";

export function SecuritySection() {
  return (
    <section className="py-24 bg-white border-t border-gray-200" id="security">
      <div className="max-w-7xl mx-auto px-6 md:px-12">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
          
          <div className="max-w-xl">
            <motion.h2 
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: false, margin: "-40px" }}
              transition={{ duration: 0.5 }}
              className="text-3xl md:text-4xl font-bold tracking-tight text-gray-900 mb-6"
            >
              Built for systems you can't afford to break.
            </motion.h2>
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: false, margin: "-40px" }}
              transition={{ duration: 0.5, delay: 0.1 }}
              className="text-lg text-gray-600 leading-relaxed mb-8"
            >
              FixFlow operates on a zero-trust model for AI generation. AI output is never trusted automatically. Permissions are strictly scoped, and production changes require explicit policy approvals.
            </motion.p>
            
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: false, margin: "-40px" }}
              transition={{ duration: 0.5, delay: 0.2 }}
              className="grid grid-cols-1 sm:grid-cols-2 gap-6"
            >
              <div className="flex gap-3">
                <Lock className="w-5 h-5 text-purple-600 shrink-0" />
                <div>
                  <h4 className="font-semibold text-gray-900 text-sm mb-1">Protected Secrets</h4>
                  <p className="text-sm text-gray-600">FixFlow never ingests or reads your environment variables or secrets.</p>
                </div>
              </div>
              <div className="flex gap-3">
                <Server className="w-5 h-5 text-purple-600 shrink-0" />
                <div>
                  <h4 className="font-semibold text-gray-900 text-sm mb-1">Scoped Access</h4>
                  <p className="text-sm text-gray-600">Read-only by default. Write access requires separate branch-level permissions.</p>
                </div>
              </div>
              <div className="flex gap-3">
                <FileText className="w-5 h-5 text-purple-600 shrink-0" />
                <div>
                  <h4 className="font-semibold text-gray-900 text-sm mb-1">Strict Policies</h4>
                  <p className="text-sm text-gray-600">Enforce approvals, tests, and branch protections before any merge.</p>
                </div>
              </div>
              <div className="flex gap-3">
                <History className="w-5 h-5 text-purple-600 shrink-0" />
                <div>
                  <h4 className="font-semibold text-gray-900 text-sm mb-1">Fully Auditable</h4>
                  <p className="text-sm text-gray-600">Every incident, analysis, and patch is logged in an immutable audit trail.</p>
                </div>
              </div>
            </motion.div>
          </div>

          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: false, margin: "-40px" }}
            transition={{ duration: 0.5, delay: 0.3 }}
            className="bg-gray-50 border border-gray-200 rounded-2xl p-8"
          >
            <h3 className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-6">Security Architecture</h3>
            
            <div className="space-y-4">
              <div className="bg-white border border-gray-200 p-4 rounded-lg flex items-center justify-between">
                <span className="text-sm font-medium text-gray-700">Code Ingestion</span>
                <span className="text-xs font-mono text-gray-500">Read-only Webhook</span>
              </div>
              <div className="bg-white border border-gray-200 p-4 rounded-lg flex items-center justify-between">
                <span className="text-sm font-medium text-gray-700">Analysis Engine</span>
                <span className="text-xs font-mono text-gray-500">Ephemeral Sandboxing</span>
              </div>
              <div className="bg-white border border-gray-200 p-4 rounded-lg flex items-center justify-between">
                <span className="text-sm font-medium text-gray-700">Patch Generation</span>
                <span className="text-xs font-mono text-gray-500">Isolated Instance</span>
              </div>
              <div className="bg-white border border-gray-200 p-4 rounded-lg flex items-center justify-between">
                <span className="text-sm font-medium text-gray-700">Recovery Action</span>
                <span className="text-xs font-mono text-purple-600 font-semibold bg-purple-50 px-2 py-1 rounded">Requires Approval</span>
              </div>
            </div>
          </motion.div>

        </div>
      </div>
    </section>
  );
}


