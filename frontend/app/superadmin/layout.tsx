"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/api/client";
import Link from "next/link";
import {
  MessageSquare,
  Settings,
  FileText,
  Shield,
  Layers,
  Users,
  Building,
  Zap,
  BookOpen,
  Plus,
  ChevronDown,
} from "lucide-react";

interface User {
  id: string;
  email: string;
  display_name: string;
  is_superuser: boolean;
}

export default function SuperadminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [conversationOpen, setConversationOpen] = useState(false);

  useEffect(() => {
    async function loadUser() {
      try {
        const res = await authFetch("/api/v1/auth/me");
        if (res.ok) {
          const data = await res.json();
          setUser(data);
          if (!data.is_superuser) {
            router.replace("/");
          }
        } else {
          router.replace("/login");
        }
      } catch (e) {
        router.replace("/login");
      } finally {
        setLoading(false);
      }
    }
    void loadUser();
  }, [router]);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50">
        <div className="text-gray-500">Laden...</div>
      </div>
    );
  }

  if (!user?.is_superuser) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50">
        <div className="text-red-600">Zugriff verweigert. Superadmin erforderlich.</div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-gray-50">
      {/* Sidebar */}
      <aside className="w-64 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-4 border-b border-gray-200">
          <Link href="/superadmin" className="flex items-center gap-2 text-xl font-bold text-gray-800">
            <Settings className="w-6 h-6" />
            Superadmin
          </Link>
        </div>

        <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
          {/* Dashboard */}
          <Link href="/superadmin" className="flex items-center gap-2 px-3 py-2 rounded-lg text-gray-700 hover:bg-gray-100">
            <Zap className="w-5 h-5" />
            Dashboard
          </Link>

          {/* Core */}
          <div className="pt-4 pb-2">
            <div className="px-3 text-xs font-semibold text-gray-500 uppercase">Core</div>
          </div>
          <Link href="/superadmin/organizations" className="flex items-center gap-2 px-3 py-2 rounded-lg text-gray-700 hover:bg-gray-100">
            <Building className="w-5 h-5" />
            Organisationen
          </Link>
          <Link href="/superadmin/users" className="flex items-center gap-2 px-3 py-2 rounded-lg text-gray-700 hover:bg-gray-100">
            <Users className="w-5 h-5" />
            Benutzer
          </Link>

          {/* Conversation Engine */}
          <div className="pt-4 pb-2">
            <div className="px-3 text-xs font-semibold text-gray-500 uppercase">Conversation Engine</div>
          </div>
          <button
            onClick={() => setConversationOpen(!conversationOpen)}
            className="w-full flex items-center justify-between px-3 py-2 rounded-lg text-gray-700 hover:bg-gray-100"
          >
            <div className="flex items-center gap-2">
              <MessageSquare className="w-5 h-5" />
              Konfiguration
            </div>
            <ChevronDown className={`w-4 h-4 transition-transform ${conversationOpen ? "rotate-180" : ""}`} />
          </button>
          {conversationOpen && (
            <div className="ml-4 space-y-1">
              <Link href="/superadmin/conversation/profiles" className="flex items-center gap-2 px-3 py-2 rounded-lg text-gray-600 hover:bg-gray-100 text-sm">
                <FileText className="w-4 h-4" />
                Dialogprofile
              </Link>
              <Link href="/superadmin/conversation/questions" className="flex items-center gap-2 px-3 py-2 rounded-lg text-gray-600 hover:bg-gray-100 text-sm">
                <Plus className="w-4 h-4" />
                Fragebausteine
              </Link>
              <Link href="/superadmin/conversation/signals" className="flex items-center gap-2 px-3 py-2 rounded-lg text-gray-600 hover:bg-gray-100 text-sm">
                <Zap className="w-4 h-4" />
                Antwortsignale
              </Link>
              <Link href="/superadmin/conversation/rules" className="flex items-center gap-2 px-3 py-2 rounded-lg text-gray-600 hover:bg-gray-100 text-sm">
                <Shield className="w-4 h-4" />
                Gesprächsregeln
              </Link>
            </div>
          )}

          {/* KnowledgeBase */}
          <div className="pt-4 pb-2">
            <div className="px-3 text-xs font-semibold text-gray-500 uppercase">KnowledgeBase</div>
          </div>
          <Link href="/superadmin/knowledge/sources" className="flex items-center gap-2 px-3 py-2 rounded-lg text-gray-700 hover:bg-gray-100">
            <BookOpen className="w-5 h-5" />
            Quellen
          </Link>

          {/* Integration Layer */}
          <div className="pt-4 pb-2">
            <div className="px-3 text-xs font-semibold text-gray-500 uppercase">Integration</div>
          </div>
          <Link href="/superadmin/integration/resources" className="flex items-center gap-2 px-3 py-2 rounded-lg text-gray-700 hover:bg-gray-100">
            <Layers className="w-5 h-5" />
            Ressourcen
          </Link>
        </nav>

        {/* User */}
        <div className="p-4 border-t border-gray-200">
          <div className="text-sm font-medium text-gray-800">{user.display_name}</div>
          <div className="text-xs text-gray-500">{user.email}</div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 p-8 overflow-y-auto">
        {children}
      </main>
    </div>
  );
}
