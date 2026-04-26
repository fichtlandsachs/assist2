import { NextRequest, NextResponse } from "next/server";

const TARGET_BASE = process.env.ADMIN_API_PROXY_BASE ?? "https://heykarl.app";

function buildTargetUrl(req: NextRequest, path: string[]) {
  const incoming = req.nextUrl;
  const targetPath = `/api/${path.join("/")}`;
  const qs = incoming.search || "";
  return `${TARGET_BASE}${targetPath}${qs}`;
}

async function proxy(req: NextRequest, path: string[]) {
  const targetUrl = buildTargetUrl(req, path);

  const headers = new Headers(req.headers);
  headers.delete("host");
  headers.delete("content-length");
  headers.delete("connection");

  const init: RequestInit = {
    method: req.method,
    headers,
    redirect: "manual",
    // GET/HEAD must not include body
    body: req.method === "GET" || req.method === "HEAD" ? undefined : await req.arrayBuffer(),
  };

  const upstream = await fetch(targetUrl, init);
  const upstreamHeaders = new Headers(upstream.headers);
  upstreamHeaders.delete("content-encoding");
  upstreamHeaders.delete("transfer-encoding");
  upstreamHeaders.delete("connection");

  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers: upstreamHeaders,
  });
}

export async function GET(req: NextRequest, context: any) {
  return proxy(req, context?.params?.path ?? []);
}

export async function POST(req: NextRequest, context: any) {
  return proxy(req, context?.params?.path ?? []);
}

export async function PUT(req: NextRequest, context: any) {
  return proxy(req, context?.params?.path ?? []);
}

export async function PATCH(req: NextRequest, context: any) {
  return proxy(req, context?.params?.path ?? []);
}

export async function DELETE(req: NextRequest, context: any) {
  return proxy(req, context?.params?.path ?? []);
}

export async function OPTIONS(req: NextRequest, context: any) {
  return proxy(req, context?.params?.path ?? []);
}
