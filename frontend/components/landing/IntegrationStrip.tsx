"use client";

import { motion } from "framer-motion";

export function IntegrationStrip() {
  const integrations = [
    "GitHub",
    "GitLab",
    "Vercel",
    "Sentry",
    "Datadog",
    "Slack",
    "PagerDuty",
  ];

  return (
    <section className="pb-16 bg-[#FAFAFA] overflow-hidden">
      <div className="max-w-[1400px] mx-auto px-6 md:px-12 flex flex-col md:flex-row items-center justify-center gap-8 md:gap-16">
        <p className="text-sm font-medium text-gray-400 whitespace-nowrap hidden md:block">
          Trusted by engineering teams at
        </p>
        
        <div className="flex flex-wrap md:flex-nowrap items-center justify-center gap-10 md:gap-16 w-full opacity-50 grayscale">
          {integrations.map((name, i) => (
            <motion.div
              key={name}
              initial={{ opacity: 0 }}
              whileInView={{ opacity: 1 }}
              viewport={{ once: false, margin: "-40px" }}
              transition={{ duration: 0.5, delay: i * 0.1 }}
              className="text-lg font-bold tracking-tight text-gray-400 hover:text-gray-900 transition-colors cursor-default"
            >
              {name}
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}


