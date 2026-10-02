"use client";

import { motion } from "framer-motion";
import { Activity, GitMerge, Search, CheckCircle2, Shield, Eye } from "lucide-react";

export function FeatureSections() {
  return (
    <>
      {/* 1. Continuous Monitoring Section */}
      <section className="py-24 bg-white" id="product">
        <div className="max-w-[1400px] mx-auto px-6 md:px-12">
          <div className="text-center mb-16">
            <motion.h2 
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: false, margin: "-40px" }}
              transition={{ duration: 0.5 }}
              className="text-4xl md:text-5xl font-bold tracking-tight text-gray-900 mb-6"
            >
              Everything you need. <br className="hidden md:block" /> Nothing you don't.
            </motion.h2>
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: false, margin: "-40px" }}
              transition={{ duration: 0.5, delay: 0.1 }}
              className="text-xl text-gray-500 max-w-2xl mx-auto"
            >
              FixFlow works continuously in the background. You don't need to manually inspect logs all day.
            </motion.p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {[
              { title: "Code Level", desc: "Monitors commits, dependency changes, and structural refactors automatically.", icon: <GitMerge className="w-6 h-6 text-indigo-600" /> },
              { title: "Build Pipeline", desc: "Integrates with CI to watch compilation steps and unit test execution.", icon: <CheckCircle2 className="w-6 h-6 text-green-600" /> },
              { title: "Deployments", desc: "Catches deployment failures, configuration drift, and infrastructure issues.", icon: <Activity className="w-6 h-6 text-orange-600" /> },
              { title: "Runtime Health", desc: "Traces exceptions, API errors, and abnormal behavior back to code.", icon: <Search className="w-6 h-6 text-purple-600" /> },
            ].map((feature, i) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: false, margin: "-40px" }}
                transition={{ duration: 0.5, delay: 0.2 + i * 0.1 }}
                className="bg-[#F8F9FA] p-8 rounded-2xl border border-gray-100 hover:shadow-md transition-shadow"
              >
                <div className="w-12 h-12 rounded-xl bg-white border border-gray-200 flex items-center justify-center mb-6 shadow-sm">
                  {feature.icon}
                </div>
                <h3 className="text-xl font-semibold text-gray-900 mb-3">{feature.title}</h3>
                <p className="text-gray-500 leading-relaxed text-sm">{feature.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* 2. Automated Repair & Verification */}
      <section className="py-24 bg-white">
        <div className="max-w-7xl mx-auto px-6 md:px-12 grid grid-cols-1 lg:grid-cols-2 gap-20 items-center">
          
          <div className="order-2 lg:order-1">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: false, margin: "-40px" }}
              transition={{ duration: 0.5 }}
              className="bg-[#FAFAFA] rounded-2xl border border-gray-200 p-8 shadow-sm"
            >
              <div className="flex items-center gap-3 mb-6">
                <Shield className="w-5 h-5 text-gray-400" />
                <span className="text-xs font-bold text-gray-400 uppercase tracking-widest">Verification Pipeline</span>
              </div>

              <div className="space-y-4">
                {[
                  { label: "Compile", status: "PASS", color: "text-green-600" },
                  { label: "Unit Tests", status: "PASS", color: "text-green-600" },
                  { label: "Integration Tests", status: "PASS", color: "text-green-600" },
                  { label: "Regression Analysis", status: "PASS", color: "text-green-600" },
                  { label: "Security Check", status: "PASS", color: "text-green-600" },
                ].map((step, i) => (
                  <div key={i} className="flex justify-between items-center text-sm border-b border-gray-100 pb-3 last:border-0 last:pb-0">
                    <span className="text-gray-700 font-medium">{step.label}</span>
                    <span className={`font-mono text-xs ${step.color}`}>✓ {step.status}</span>
                  </div>
                ))}
              </div>
              
              <div className="mt-8 bg-white border border-gray-200 rounded-lg p-4 flex justify-between items-center">
                <div>
                  <div className="text-[10px] text-gray-500 font-bold tracking-widest uppercase mb-1">Confidence Grade</div>
                  <div className="text-2xl font-semibold text-gray-900">96%</div>
                </div>
                <div className="text-right">
                  <div className="text-[10px] text-gray-500 font-bold tracking-widest uppercase mb-1">Risk Assessment</div>
                  <div className="inline-flex px-2 py-0.5 rounded bg-gray-100 text-gray-700 text-xs font-semibold">LOW</div>
                </div>
              </div>
            </motion.div>
          </div>

          <div className="order-1 lg:order-2 max-w-xl">
            <motion.h2 
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: false, margin: "-40px" }}
              transition={{ duration: 0.5 }}
              className="text-3xl md:text-4xl font-bold tracking-tight text-gray-900 mb-6"
            >
              Never trust the patch blindly.
            </motion.h2>
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: false, margin: "-40px" }}
              transition={{ duration: 0.5, delay: 0.1 }}
              className="text-lg text-gray-600 leading-relaxed mb-6"
            >
              FixFlow doesn't just guess a fix. It generates coordinated, multi-file repair suggestions and rigorously tests them in a sandboxed environment before proposing them to you.
            </motion.p>
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: false, margin: "-40px" }}
              transition={{ duration: 0.5, delay: 0.2 }}
              className="text-lg text-gray-600 leading-relaxed"
            >
              Every proposed change is assessed for regressions, type safety, and security vulnerabilities. Autonomy where it helps; proof where it matters.
            </motion.p>
          </div>

        </div>
      </section>

      {/* 3. Human Oversight */}
      <section className="py-24 bg-[#111] text-white">
        <div className="max-w-7xl mx-auto px-6 md:px-12 text-center">
          <motion.div
             initial={{ opacity: 0, y: 20 }}
             whileInView={{ opacity: 1, y: 0 }}
             viewport={{ once: false, margin: "-40px" }}
             transition={{ duration: 0.5 }}
             className="w-12 h-12 rounded-full bg-white/10 flex items-center justify-center mx-auto mb-6"
          >
            <Eye className="w-6 h-6 text-gray-300" />
          </motion.div>
          <motion.h2 
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: false, margin: "-40px" }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="text-3xl md:text-4xl font-bold tracking-tight mb-6"
          >
            Autonomy where it helps. Control where it matters.
          </motion.h2>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: false, margin: "-40px" }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="text-lg text-gray-400 max-w-2xl mx-auto mb-16"
          >
            FixFlow is designed around progressive autonomy. It will detect, analyze, and prepare repairs independently, but it will never merge to production without human approval.
          </motion.p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl mx-auto text-left">
            <motion.div 
               initial={{ opacity: 0, x: -20 }}
               whileInView={{ opacity: 1, x: 0 }}
               viewport={{ once: false, margin: "-40px" }}
               transition={{ duration: 0.5, delay: 0.3 }}
               className="bg-white/5 border border-white/10 rounded-2xl p-8"
            >
              <h3 className="text-lg font-semibold text-white mb-6 flex items-center gap-2"><CheckCircle2 className="w-5 h-5 text-gray-400"/> Fully Autonomous</h3>
              <ul className="space-y-4 text-sm text-gray-400">
                <li className="flex gap-3"><span className="text-gray-600">—</span> Detect failures</li>
                <li className="flex gap-3"><span className="text-gray-600">—</span> Analyze logs and traces</li>
                <li className="flex gap-3"><span className="text-gray-600">—</span> Explain root causes</li>
                <li className="flex gap-3"><span className="text-gray-600">—</span> Propose verified patches</li>
              </ul>
            </motion.div>

            <motion.div 
               initial={{ opacity: 0, x: 20 }}
               whileInView={{ opacity: 1, x: 0 }}
               viewport={{ once: false, margin: "-40px" }}
               transition={{ duration: 0.5, delay: 0.4 }}
               className="bg-white/5 border border-white/10 rounded-2xl p-8"
            >
              <h3 className="text-lg font-semibold text-white mb-6 flex items-center gap-2"><Shield className="w-5 h-5 text-purple-400"/> Requires Approval</h3>
              <ul className="space-y-4 text-sm text-gray-400">
                <li className="flex gap-3"><span className="text-gray-600">—</span> Create Pull Requests</li>
                <li className="flex gap-3"><span className="text-gray-600">—</span> Merge to default branch</li>
                <li className="flex gap-3"><span className="text-gray-600">—</span> Trigger production deployment</li>
                <li className="flex gap-3"><span className="text-gray-600">—</span> Rollback live environments</li>
              </ul>
            </motion.div>
          </div>
        </div>
      </section>
    </>
  );
}


