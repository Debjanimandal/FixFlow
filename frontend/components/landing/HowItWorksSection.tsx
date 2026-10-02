"use client";

import { motion } from "framer-motion";

export function HowItWorksSection() {
  const steps = [
    { num: "01", title: "Connect", desc: "Connect GitHub and the rest of your software stack." },
    { num: "02", title: "Observe", desc: "FixFlow continuously monitors code changes, builds, tests, deployments, and runtime signals." },
    { num: "03", title: "Detect", desc: "Failures and abnormal behavior become incidents automatically." },
    { num: "04", title: "Understand", desc: "FixFlow correlates logs, code changes, dependencies, and system context." },
    { num: "05", title: "Repair", desc: "AI generates coordinated, multi-file repair suggestions." },
    { num: "06", title: "Verify", desc: "The proposed repair is tested and assessed for regression and security risk." },
    { num: "07", title: "Recover", desc: "A reviewable pull request or recovery workflow is prepared." },
    { num: "08", title: "Learn", desc: "Resolved incidents become useful historical context for future automated repairs." },
  ];

  return (
    <section className="py-24 md:py-32 bg-white" id="how-it-works">
      <div className="max-w-7xl mx-auto px-6 md:px-12">
        <div className="text-center mb-16 md:mb-24">
          <motion.h2 
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: false, margin: "-40px" }}
            transition={{ duration: 0.5 }}
            className="text-3xl md:text-4xl font-bold tracking-tight text-gray-900"
          >
            How FixFlow works
          </motion.h2>
        </div>

        <div className="relative">
          {/* Central Line (Desktop) */}
          <div className="hidden md:block absolute left-1/2 top-0 bottom-0 w-px bg-gray-200 -translate-x-1/2" />
          
          <div className="space-y-12 md:space-y-0 relative">
            {steps.map((step, i) => (
              <div 
                key={step.num} 
                className={`md:w-1/2 flex flex-col md:flex-row relative ${i % 2 === 0 ? "md:pr-16 md:ml-0 md:text-right md:justify-end" : "md:pl-16 md:ml-auto md:justify-start"}`}
              >
                {/* Timeline Dot (Desktop) */}
                <div className={`hidden md:flex absolute top-6 -translate-y-1/2 w-8 h-8 rounded-full bg-white border-2 border-gray-200 items-center justify-center text-xs font-bold text-gray-400 z-10 ${i % 2 === 0 ? "-right-4" : "-left-4"}`}>
                  {step.num}
                </div>

                <motion.div
                  initial={{ opacity: 0, x: i % 2 === 0 ? -30 : 30 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: false, margin: "-40px" }}
                  transition={{ duration: 0.5, delay: 0.1 }}
                  className="bg-gray-50 border border-gray-100 rounded-2xl p-8 w-full max-w-md shadow-sm hover:shadow-md transition-shadow"
                >
                  <div className="text-[10px] font-bold text-purple-600 uppercase tracking-wider mb-2 md:hidden">Step {step.num}</div>
                  <h3 className="text-xl font-semibold text-gray-900 mb-3">{step.title}</h3>
                  <p className="text-gray-600 text-sm leading-relaxed">{step.desc}</p>
                </motion.div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}


