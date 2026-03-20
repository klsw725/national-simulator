import { NextRequest, NextResponse } from "next/server";

const GATEWAY_URL = process.env.GATEWAY_URL || "http://localhost:4000";

async function proxyRequest(req: NextRequest) {
  const url = new URL(req.url);
  const targetUrl = `${GATEWAY_URL}${url.pathname}${url.search}`;

  const headers = new Headers();
  req.headers.forEach((value, key) => {
    if (
      key !== "host" &&
      key !== "connection" &&
      key !== "transfer-encoding"
    ) {
      headers.set(key, value);
    }
  });

  try {
    const upstream = await fetch(targetUrl, {
      method: req.method,
      headers,
      body:
        req.method !== "GET" && req.method !== "HEAD"
          ? await req.text()
          : undefined,
    });

    const responseHeaders = new Headers();
    upstream.headers.forEach((value, key) => {
      if (key !== "transfer-encoding" && key !== "connection") {
        responseHeaders.set(key, value);
      }
    });

    const body = await upstream.arrayBuffer();
    return new NextResponse(body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: responseHeaders,
    });
  } catch {
    return NextResponse.json(
      { error: "Gateway unreachable" },
      { status: 502 }
    );
  }
}

export const GET = proxyRequest;
export const POST = proxyRequest;
export const PUT = proxyRequest;
export const DELETE = proxyRequest;
export const PATCH = proxyRequest;
