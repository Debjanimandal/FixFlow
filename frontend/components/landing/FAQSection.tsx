"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { githubLoginUrl } from "@/lib/api-client";

export function FAQSection() {
  const faqs = [
    {
      q: "What is FixFlow?",
      a: "FixFlow is an autonomous software reliability platform that monitors your codebase, detects failures, traces their root cause, and proposes verified repairs.",
    },
    {
      q: "How does FixFlow detect failures?",
      a: "FixFlow ingests webhooks from GitHub, Vercel, Datadog, Sentry, and CI/CD pipelines to monitor commits, build statuses, and runtime logs continuously.",
    },
    {
      q: "Does FixFlow automatically change my code?",
      a: "No. FixFlow generates and verifies patches in a sandboxed environment, then prepares a Pull Request for human review. It does not merge without approval.",
    },
    {
      q: "How does verification work?",
      a: "Before a patch is proposed, FixFlow simulates the fix, compiles the code, runs the test suite, and checks for common security regressions.",
    },
    {
      q: "Does FixFlow work with AI coding agents?",
      a: "Yes. FixFlow acts as the reliability and safety net that catches regressions caused by both human engineers and AI coding assistants.",
    },
  ];

  return (
    <section className="py-24 bg-white" id="faq">
      <div className="max-w-3xl mx-auto px-6 md:px-12">
        <div className="text-center mb-16">
          <motion.h2 
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: false, margin: "-40px" }}
            transition={{ duration: 0.5 }}
            className="text-3xl font-bold tracking-tight text-gray-900"
          >
            Frequently asked questions
          </motion.h2>
        </div>

        <div className="space-y-8">
          {faqs.map((faq, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: false, margin: "-40px" }}
              transition={{ duration: 0.5, delay: i * 0.1 }}
              className="border-b border-gray-100 pb-8 last:border-0 last:pb-0"
            >
              <h3 className="text-lg font-semibold text-gray-900 mb-3">{faq.q}</h3>
              <p className="text-gray-600 leading-relaxed">{faq.a}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

export function FinalCTA() {
  return (
    <section className="py-32 bg-[#FAFAFA] border-t border-gray-200">
      <div className="max-w-4xl mx-auto px-6 md:px-12 text-center">
        <motion.h2 
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: false, margin: "-40px" }}
          transition={{ duration: 0.5 }}
          className="text-4xl md:text-5xl font-bold tracking-tight text-gray-900 mb-6"
        >
          Let your software handle more of its own recovery.
        </motion.h2>
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: false, margin: "-40px" }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="text-xl text-gray-600 mb-10 max-w-2xl mx-auto"
        >
          Connect your repository and start monitoring the software that keeps your business running.
        </motion.p>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: false, margin: "-40px" }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="flex flex-col sm:flex-row items-center justify-center gap-4"
        >
          <Link
            href={githubLoginUrl}
            className="w-full sm:w-auto px-8 py-4 bg-[#111] text-white rounded-lg font-medium text-[15px] hover:bg-gray-900 transition-colors flex items-center justify-center gap-2 group"
          >
            Get started for free
            <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
          </Link>
          <Link
            href="#product"
            className="w-full sm:w-auto px-8 py-4 bg-white text-gray-900 border border-gray-200 rounded-lg font-medium text-[15px] hover:bg-gray-50 transition-colors flex items-center justify-center"
          >
            Explore the platform
          </Link>
        </motion.div>
      </div>
    </section>
  );
}


