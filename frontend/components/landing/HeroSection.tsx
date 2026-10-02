"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, Play, Check } from "lucide-react";
import { ProductPreview } from "./ProductPreview";
import { githubLoginUrl } from "@/lib/api-client";

export function HeroSection() {
  return (
    <section className="relative pt-32 pb-16 lg:pt-40 lg:pb-20 overflow-hidden bg-[#FAFAFA]">
      <div className="max-w-[1400px] mx-auto px-6 md:px-12">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
          {/* Left Text Content */}
          <div className="lg:col-span-5 flex flex-col items-start text-left z-10">
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: false, margin: "0px" }}
              transition={{ duration: 0.5 }}
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white border border-gray-200 text-xs font-semibold text-gray-600 mb-8 shadow-sm hover:shadow-md transition-shadow cursor-pointer"
            >
              <span className="text-[#581C87]">✨</span> Trusted by engineering teams worldwide <ArrowRight className="w-3.5 h-3.5 ml-1" />
            </motion.div>

            <motion.h1
              initial={{ opacity: 0, y: 15 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: false, margin: "0px" }}
              transition={{ duration: 0.5, delay: 0.1 }}
              className="text-5xl md:text-6xl lg:text-[64px] font-bold tracking-tight text-[#111] leading-[1.05] mb-6"
            >
              Your Code. One Platform. Actually Fixed.
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 15 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: false, margin: "0px" }}
              transition={{ duration: 0.5, delay: 0.2 }}
              className="text-lg md:text-xl text-gray-600 leading-relaxed mb-8 max-w-lg"
            >
              FixFlow brings your deployments, tests, logs, and root causes into one autonomous workspace so nothing slips through.
            </motion.p>

            {/* Checkmarks Grid */}
            <motion.div
              initial={{ opacity: 0, y: 15 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: false, margin: "0px" }}
              transition={{ duration: 0.5, delay: 0.3 }}
              className="grid grid-cols-2 gap-y-3 gap-x-6 mb-10 w-full max-w-md"
            >
              {[
                "Connects to GitHub",
                "Ingests Vercel logs",
                "Traces root causes",
                "Verifies safe patches",
                "Auto-generates PRs",
                "Human approval flow"
              ].map((item, i) => (
                <div key={i} className="flex items-center gap-2 text-sm font-medium text-gray-700">
                  <Check className="w-4 h-4 text-green-500 shrink-0" strokeWidth={3} />
                  {item}
                </div>
              ))}
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 15 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: false, margin: "0px" }}
              transition={{ duration: 0.5, delay: 0.4 }}
              className="flex flex-col sm:flex-row items-center gap-4 w-full sm:w-auto"
            >
              <Link
                href={githubLoginUrl}
                className="w-full sm:w-auto px-8 py-3.5 bg-[#4F46E5] text-white rounded-lg font-semibold text-[15px] hover:bg-[#4338CA] transition-colors flex items-center justify-center gap-2 group shadow-lg shadow-indigo-200"
              >
                Get started for Free
                <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
              </Link>
              <Link
                href="#how-it-works"
                className="w-full sm:w-auto px-8 py-3.5 bg-white text-gray-900 border border-gray-200 rounded-lg font-semibold text-[15px] hover:bg-gray-50 transition-colors flex items-center justify-center gap-2 shadow-sm"
              >
                Watch Demo
              </Link>
            </motion.div>
          </div>

          {/* Right Image Content */}
          <div className="lg:col-span-7 relative z-0 mt-12 lg:mt-0 w-full flex justify-center lg:justify-end">
            <motion.div
              initial={{ opacity: 0, x: 40 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: false, margin: "0px" }}
              transition={{ duration: 0.7, delay: 0.3 }}
              className="relative w-full"
            >
              {/* Decorative background shape */}
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full h-[80%] bg-indigo-100/80 rounded-full blur-[100px] -z-10 opacity-60" />
              
              <ProductPreview />
            </motion.div>
          </div>
        </div>
      </div>
    </section>
  );
}


