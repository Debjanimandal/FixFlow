"use client";

import { motion } from "framer-motion";
import { ArrowDown } from "lucide-react";

export function ProblemSection() {
  const steps = [
    { label: "CODE CHANGE", color: "bg-blue-50 text-blue-700 border-blue-200" },
    { label: "DEPENDENCY", color: "bg-indigo-50 text-indigo-700 border-indigo-200" },
    { label: "API CONTRACT", color: "bg-purple-50 text-purple-700 border-purple-200" },
    { label: "TEST", color: "bg-pink-50 text-pink-700 border-pink-200" },
    { label: "DEPLOYMENT", color: "bg-rose-50 text-rose-700 border-rose-200" },
    { label: "RUNTIME", color: "bg-red-50 text-red-700 border-red-200" },
  ];

  return (
    <section className="py-24 md:py-32 bg-white" id="problem">
      <div className="max-w-7xl mx-auto px-6 md:px-12">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 lg:gap-24 items-center">
          
          {/* Text Content */}
          <div className="max-w-xl">
            <motion.h2 
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: false, margin: "-40px" }}
              transition={{ duration: 0.5 }}
              className="text-3xl md:text-4xl lg:text-5xl font-bold tracking-tight text-gray-900 mb-6 leading-[1.15]"
            >
              Modern software moves faster than humans can debug it.
            </motion.h2>
            
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: false, margin: "-40px" }}
              transition={{ duration: 0.5, delay: 0.1 }}
              className="space-y-5 text-lg text-gray-600 leading-relaxed"
            >
              <p>
                Developers are shipping faster than ever. AI coding tools are exponentially increasing the volume of code changes. Services interact, dependencies grow, and deployments happen continuously.
              </p>
              <p>
                In a complex system, failures rarely originate exactly where they appear. One small structural change can silently break something five layers away in production.
              </p>
            </motion.div>
          </div>

          {/* Visual Content */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: false, margin: "-40px" }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="bg-gray-50 rounded-2xl border border-gray-200 p-8 md:p-12 flex flex-col items-center justify-center relative"
          >
            <div className="flex flex-col items-center gap-2 w-full max-w-[240px]">
              {steps.map((step, i) => (
                <div key={step.label} className="flex flex-col items-center w-full">
                  <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: false, margin: "-40px" }}
                    transition={{ duration: 0.4, delay: 0.3 + i * 0.1 }}
                    className={`w-full py-2.5 px-4 rounded-lg border text-xs font-bold tracking-widest text-center shadow-sm ${step.color}`}
                  >
                    {step.label}
                  </motion.div>
                  {i < steps.length - 1 && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      whileInView={{ opacity: 1, height: "16px" }}
                      viewport={{ once: false, margin: "-40px" }}
                      transition={{ duration: 0.3, delay: 0.4 + i * 0.1 }}
                      className="text-gray-300 py-1"
                    >
                      <ArrowDown className="w-4 h-4" />
                    </motion.div>
                  )}
                </div>
              ))}
            </div>

            <motion.div
              initial={{ opacity: 0 }}
              whileInView={{ opacity: 1 }}
              viewport={{ once: false, margin: "-40px" }}
              transition={{ duration: 0.5, delay: 1.1 }}
              className="mt-8 text-center"
            >
              <p className="text-sm font-medium text-gray-500 max-w-[260px]">
                One small change can break something five layers away.
              </p>
            </motion.div>
          </motion.div>

        </div>
      </div>
    </section>
  );
}


