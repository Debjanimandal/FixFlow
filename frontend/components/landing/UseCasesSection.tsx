"use client";

import { motion } from "framer-motion";

export function UseCasesSection() {
  const useCases = [
    {
      title: "AI-generated code changes",
      desc: "Catch downstream breakage before it reaches production.",
    },
    {
      title: "Deployment failures",
      desc: "Understand exactly why the latest deployment failed and how to fix it.",
    },
    {
      title: "API contract changes",
      desc: "Trace contract changes across dependent services automatically.",
    },
    {
      title: "Dependency conflicts",
      desc: "Identify what changed in your package registry and what it affected.",
    },
    {
      title: "Runtime incidents",
      desc: "Connect runtime symptoms back to the specific code commits that caused them.",
    },
    {
      title: "Growing engineering teams",
      desc: "Keep operational knowledge in the system instead of in someone's head.",
    },
  ];

  return (
    <section className="py-24 bg-[#FAFAFA]">
      <div className="max-w-7xl mx-auto px-6 md:px-12">
        <div className="text-center mb-16">
          <motion.h2 
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: false, margin: "-40px" }}
            transition={{ duration: 0.5 }}
            className="text-3xl font-bold tracking-tight text-gray-900"
          >
            Built for modern engineering teams
          </motion.h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 max-w-5xl mx-auto">
          {useCases.map((uc, i) => (
            <motion.div
              key={uc.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: false, margin: "-40px" }}
              transition={{ duration: 0.5, delay: i * 0.1 }}
              className="bg-white border border-gray-200 p-6 rounded-xl shadow-sm"
            >
              <h3 className="font-semibold text-gray-900 mb-2">{uc.title}</h3>
              <p className="text-sm text-gray-600 leading-relaxed">{uc.desc}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}


