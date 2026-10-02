import { motion } from "framer-motion";
import { Check, X, AlertCircle, RefreshCw, ArrowRight } from "lucide-react";

export function ProductPreview() {
  return (
    <div className="relative rounded-2xl border border-gray-200 bg-white shadow-2xl flex flex-col h-auto max-h-[600px] overflow-hidden">
      {/* Fake Browser Window Header */}
      <div className="h-12 bg-gray-50 border-b border-gray-200 flex items-center px-4 gap-2 shrink-0 z-10">
        <div className="flex gap-1.5 ml-2">
          <div className="w-3 h-3 rounded-full bg-[#FF5F56] border border-[#E0443E]" />
          <div className="w-3 h-3 rounded-full bg-[#FFBD2E] border border-[#DEA123]" />
          <div className="w-3 h-3 rounded-full bg-[#27C93F] border border-[#1AAB29]" />
        </div>
        <div className="mx-auto bg-white border border-gray-200 rounded-md text-[11px] text-gray-400 font-mono px-4 py-1 flex items-center gap-2 shadow-sm truncate max-w-[200px] sm:max-w-none">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" className="shrink-0"><rect x="2" y="2" width="20" height="20" rx="4" stroke="currentColor" strokeWidth="2" /><path d="M7 12h10M12 7v10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg>
          <span className="truncate">app.patchr.dev/dashboard/incidents/inc-912</span>
        </div>
      </div>

      {/* Simplified UI Representation */}
      <div className="p-5 md:p-6 bg-[#FAFAFA] flex-1 font-sans overflow-y-auto no-scrollbar">
        
        {/* Top Header */}
        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-4 mb-6">
          <div>
            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full border border-red-200 bg-red-50 text-red-600 text-[10px] font-bold uppercase mb-3 tracking-wide shadow-sm">
              <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
              Deployment Failure
            </div>
            <h3 className="text-lg md:text-xl font-semibold text-gray-900 mb-1 leading-tight">Module not found: Can't resolve '@/components/UserProfile'</h3>
            <p className="text-xs text-gray-500 font-mono">acme-inc/my-saas-app · commit a3f8d2c</p>
          </div>
          <button className="hidden sm:flex items-center gap-2 px-4 py-2 bg-[#111] text-white rounded-lg text-sm font-medium shrink-0 hover:bg-gray-800 transition-colors">
            Review PR <ArrowRight className="w-4 h-4" />
          </button>
        </div>

        {/* Workflow Stack */}
        <div className="flex flex-col gap-4 relative">
          {/* Vertical Connection Line */}
          <div className="absolute left-6 top-0 bottom-0 w-px bg-purple-200 z-0" />

          {/* Card 1: Root Cause */}
          <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm relative z-10">
            <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-2">1. Root Cause Analysis</div>
            <p className="text-xs md:text-sm text-gray-700 leading-relaxed mb-3">
              The file <code className="text-[11px] bg-gray-100 px-1 py-0.5 rounded text-gray-800 border border-gray-200">UserProfile.tsx</code> was moved to a nested directory, but import paths in dependent files were not updated.
            </p>
            <div className="flex items-center gap-2 text-[11px] text-amber-700 bg-amber-50 px-2.5 py-1.5 rounded-md border border-amber-100 font-medium">
              <AlertCircle className="w-3.5 h-3.5" />
              3 downstream files affected
            </div>
          </div>

          {/* Card 2: Patch Generation */}
          <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm relative z-10">
            <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-2 flex items-center justify-between">
              <span>2. Patch Generation</span>
              <span className="text-[10px] font-medium text-gray-500 flex items-center gap-1 bg-gray-50 px-2 py-0.5 rounded border border-gray-100">
                <RefreshCw className="w-3 h-3" /> Coordinated repair
              </span>
            </div>
            
            <div className="rounded-lg border border-gray-200 overflow-hidden text-[11px] font-mono shadow-inner">
              <div className="bg-red-50/50 px-3 py-2.5 text-red-700 border-b border-gray-100 flex gap-3">
                <span className="opacity-40 select-none">-</span>
                <span className="break-all">import UserProfile from '@/components/UserProfile';</span>
              </div>
              <div className="bg-green-50/50 px-3 py-2.5 text-green-700 flex gap-3">
                <span className="opacity-40 select-none">+</span>
                <span className="break-all">import UserProfile from '@/components/user/UserProfile';</span>
              </div>
            </div>
          </div>

          {/* Card 3: Verification */}
          <div className="bg-white border border-purple-200 rounded-xl p-4 shadow-sm shadow-purple-100/50 relative z-10">
            <div className="text-[10px] font-bold text-purple-600 uppercase tracking-wider mb-3">3. Verification Pipeline</div>
            
            <div className="flex flex-col gap-2">
              <div className="flex justify-between items-center text-xs bg-gray-50/50 px-3 py-2 rounded-md border border-gray-100">
                <span className="text-gray-700 font-medium">Compilation</span>
                <span className="flex items-center gap-1.5 text-green-600 font-semibold"><Check className="w-3.5 h-3.5" /> Pass</span>
              </div>
              <div className="flex justify-between items-center text-xs bg-gray-50/50 px-3 py-2 rounded-md border border-gray-100">
                <span className="text-gray-700 font-medium">Unit Tests</span>
                <span className="flex items-center gap-1.5 text-green-600 font-semibold"><Check className="w-3.5 h-3.5" /> Pass</span>
              </div>
              <div className="flex justify-between items-center text-xs bg-gray-50/50 px-3 py-2 rounded-md border border-gray-100">
                <span className="text-gray-700 font-medium">Security Check</span>
                <span className="flex items-center gap-1.5 text-green-600 font-semibold"><Check className="w-3.5 h-3.5" /> Pass</span>
              </div>
            </div>
          </div>
          
        </div>
      </div>
    </div>
  );
}


