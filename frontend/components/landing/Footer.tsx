"use client";

import Link from "next/link";

export function Footer() {
  return (
    <footer className="bg-white border-t border-gray-200 py-16">
      <div className="max-w-7xl mx-auto px-6 md:px-12">
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-8 lg:gap-12 mb-16">
          <div className="col-span-2 lg:col-span-2">
            <Link href="/" className="flex items-center gap-2 mb-4">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                <rect x="2" y="2" width="20" height="20" rx="4" stroke="#111" strokeWidth="1.5" />
                <path d="M7 12h10M12 7v10" stroke="#111" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
              <span className="font-semibold text-lg tracking-tight">FixFlow</span>
            </Link>
            <p className="text-sm text-gray-500 max-w-xs leading-relaxed">
              Autonomous software reliability platform. FixFlow continuously monitors your codebase, detects failures, and proposes verified repairs.
            </p>
          </div>

          <div>
            <h4 className="text-sm font-semibold text-gray-900 mb-4">Product</h4>
            <ul className="flex flex-col gap-3">
              <li><Link href="/dashboard" className="text-sm text-gray-500 hover:text-gray-900 transition-colors">Dashboard</Link></li>
              <li><Link href="#" className="text-sm text-gray-500 hover:text-gray-900 transition-colors">Monitoring</Link></li>
              <li><Link href="/dashboard/incidents" className="text-sm text-gray-500 hover:text-gray-900 transition-colors">Incidents</Link></li>
              <li><Link href="#" className="text-sm text-gray-500 hover:text-gray-900 transition-colors">Integrations</Link></li>
              <li><Link href="#" className="text-sm text-gray-500 hover:text-gray-900 transition-colors">Pricing</Link></li>
            </ul>
          </div>

          <div>
            <h4 className="text-sm font-semibold text-gray-900 mb-4">Resources</h4>
            <ul className="flex flex-col gap-3">
              <li><Link href="#" className="text-sm text-gray-500 hover:text-gray-900 transition-colors">Documentation</Link></li>
              <li><Link href="#" className="text-sm text-gray-500 hover:text-gray-900 transition-colors">Architecture</Link></li>
              <li><Link href="#" className="text-sm text-gray-500 hover:text-gray-900 transition-colors">Changelog</Link></li>
              <li><Link href="#" className="text-sm text-gray-500 hover:text-gray-900 transition-colors">Blog</Link></li>
            </ul>
          </div>

          <div>
            <h4 className="text-sm font-semibold text-gray-900 mb-4">Company</h4>
            <ul className="flex flex-col gap-3">
              <li><Link href="#" className="text-sm text-gray-500 hover:text-gray-900 transition-colors">About</Link></li>
              <li><Link href="#" className="text-sm text-gray-500 hover:text-gray-900 transition-colors">Contact</Link></li>
              <li><Link href="#" className="text-sm text-gray-500 hover:text-gray-900 transition-colors">Careers</Link></li>
            </ul>
          </div>
        </div>

        <div className="pt-8 border-t border-gray-100 flex flex-col md:flex-row justify-between items-center gap-4">
          <p className="text-sm text-gray-500">
            © {new Date().getFullYear()} FixFlow Inc. All rights reserved.
          </p>
          <div className="flex items-center gap-6">
            <Link href="#" className="text-sm text-gray-500 hover:text-gray-900 transition-colors">Privacy</Link>
            <Link href="#" className="text-sm text-gray-500 hover:text-gray-900 transition-colors">Terms</Link>
            <Link href="#" className="text-sm text-gray-500 hover:text-gray-900 transition-colors">Security</Link>
          </div>
        </div>
      </div>
    </footer>
  );
}


