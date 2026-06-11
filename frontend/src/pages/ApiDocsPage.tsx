import { useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import { copyToClipboard } from '@/lib/utils';
import { useAuth } from '@/context/AuthContext';
import { LogIn } from 'lucide-react';
import { Copy, Check, Play, Loader2, AlertTriangle, ChevronDown, ChevronUp } from 'lucide-react';
import Logo from '@/components/Logo';

const BASE = import.meta.env.VITE_GATEWAY_URL || 'http://localhost:8080';

// ── tiny helpers ─────────────────────────────────────────────────────────────
function useCopy() {
  const [copied, setCopied] = useState<string | null>(null);
  const copy = (text: string, id: string) => {
    copyToClipboard(text);
    setCopied(id);
    setTimeout(() => setCopied(null), 2000);
  };
  return { copied, copy };
}

function CodeBlock({ code, id, lang = 'bash' }: { code: string; id: string; lang?: string }) {
  const { copied, copy } = useCopy();
  return (
    <div className="relative group">
      <pre className={`language-${lang} bg-gray-900 text-gray-100 rounded-lg p-4 text-xs overflow-x-auto leading-relaxed whitespace-pre`}>
        {code}
      </pre>
      <button
        onClick={() => copy(code, id)}
        className="absolute top-2 right-2 p-1.5 rounded bg-gray-700 hover:bg-gray-600 text-gray-300 opacity-0 group-hover:opacity-100 transition-opacity"
        title="Copy"
      >
        {copied === id ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5" />}
      </button>
    </div>
  );
}

function Badge({ color, children }: { color: string; children: React.ReactNode }) {
  return <span className={`inline-block text-xs font-mono font-semibold px-2 py-0.5 rounded ${color}`}>{children}</span>;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-8">
      <h3 className="text-base font-semibold text-gray-900 mb-3 pb-2 border-b border-gray-200">{title}</h3>
      {children}
    </div>
  );
}

function ParamRow({ name, type, required, desc }: { name: string; type: string; required?: boolean; desc: string }) {
  return (
    <tr className="border-b border-gray-100 last:border-0">
      <td className="py-2 pr-3 align-top">
        <span className="font-mono text-xs text-gray-800">{name}</span>
        {required && <span className="ml-1 text-red-500 text-xs">*</span>}
      </td>
      <td className="py-2 pr-3 align-top">
        <span className="font-mono text-xs text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded">{type}</span>
      </td>
      <td className="py-2 text-xs text-gray-600 align-top">{desc}</td>
    </tr>
  );
}

// ── code example templates ────────────────────────────────────────────────────
const makeCurl = (apiKey: string, model: string, message: string, temp: number, maxTok: number | '') =>
  `curl -X POST ${BASE}/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer ${apiKey || '<YOUR_API_KEY>'}" \\
  -d '{
    "model": "${model || 'llama3.2'}",
    "messages": [
      {"role": "user", "content": "${message || 'Hello, how can you help me?'}"}
    ],
    "temperature": ${temp}${maxTok !== '' ? `,\n    "max_tokens": ${maxTok}` : ''}
  }'`;

const makePython = (apiKey: string, model: string, message: string, temp: number, maxTok: number | '') =>
  `from openai import OpenAI

client = OpenAI(
    base_url="${BASE}/v1",
    api_key="${apiKey || '<YOUR_API_KEY>'}"
)

response = client.chat.completions.create(
    model="${model || 'llama3.2'}",
    messages=[
        {"role": "user", "content": "${message || 'Hello, how can you help me?'}"}
    ],
    temperature=${temp}${maxTok !== '' ? `,\n    max_tokens=${maxTok}` : ''}
)

print(response.choices[0].message.content)`;

const makeJs = (apiKey: string, model: string, message: string, temp: number, maxTok: number | '') =>
  `const response = await fetch('${BASE}/v1/chat/completions', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ${apiKey || '<YOUR_API_KEY>'}',
  },
  body: JSON.stringify({
    model: '${model || 'llama3.2'}',
    messages: [
      { role: 'user', content: '${message || 'Hello, how can you help me?'}' }
    ],
    temperature: ${temp}${maxTok !== '' ? `,\n    max_tokens: ${maxTok}` : ''}
  }),
});

const data = await response.json();
console.log(data.choices[0].message.content);`;

// ── tabs ──────────────────────────────────────────────────────────────────────
type Tab = 'overview' | 'reference' | 'sandbox';

export default function ApiDocsPage() {
  const [tab, setTab] = useState<Tab>('overview');
  const { isAuthenticated, user } = useAuth();

  return (
    <div className="min-h-screen bg-[#F9FAFB]">
      {/* Standalone header */}
      <header className="bg-slate-900 text-white px-6 py-3 flex items-center gap-3">
        <Logo className="w-6 h-6 text-white" />
        <span className="font-semibold text-sm">Synapse AI Gateway</span>
        <span className="text-white/40 text-sm mx-1">·</span>
        <span className="text-white/70 text-sm">API Documentation</span>
        <div className="ml-auto flex items-center gap-3">
          {isAuthenticated && user ? (
            <Link to="/" className="text-xs text-white/70 hover:text-white transition-colors">
              ← Admin Console
            </Link>
          ) : (
            <Link
              to="/login"
              className="flex items-center gap-1.5 text-xs bg-white/10 hover:bg-white/20 px-3 py-1.5 rounded transition-colors"
            >
              <LogIn className="w-3.5 h-3.5" /> Sign in
            </Link>
          )}
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">API Documentation</h2>
          <p className="text-sm text-gray-500 mt-0.5">OpenAI-compatible chat completions gateway</p>
        </div>
        <Badge color="bg-green-100 text-green-800">v1</Badge>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 bg-gray-100 rounded-lg p-1 w-fit">
        {([['overview', 'Overview'], ['reference', 'Endpoint Reference'], ['sandbox', 'Live Sandbox']] as [Tab, string][]).map(([t, label]) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${tab === t ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-900'}`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'overview' && <OverviewTab />}
      {tab === 'reference' && <ReferenceTab />}
      {tab === 'sandbox' && <SandboxTab isAuthenticated={isAuthenticated} />}
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// OVERVIEW TAB
// ══════════════════════════════════════════════════════════════════════════════
function OverviewTab() {
  const [lang, setLang] = useState<'curl' | 'python' | 'js'>('curl');
  const exampleKey = 'your-team-api-key-here';
  const exampleMsg = 'What is the interest rate on YourOrg savings accounts?';

  const examples = {
    curl: makeCurl(exampleKey, 'llama3.2', exampleMsg, 0.7, ''),
    python: makePython(exampleKey, 'llama3.2', exampleMsg, 0.7, ''),
    js: makeJs(exampleKey, 'llama3.2', exampleMsg, 0.7, ''),
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Left: docs */}
      <div className="space-y-6">
        <Section title="What is the Synapse AI Gateway?">
          <p className="text-sm text-gray-600 leading-relaxed">
            The Synapse AI Gateway is an on-premises proxy that sits between your applications and the
            underlying language model. Every request passes through authentication, rate limiting,
            system prompt injection, and DLP scanning before being forwarded to the model.
          </p>
          <div className="mt-3 bg-gray-50 border border-gray-200 rounded-lg p-4 space-y-2">
            {[
              ['Base URL', `${BASE}`],
              ['Protocol', 'HTTP/HTTPS'],
              ['Format', 'OpenAI-compatible JSON'],
              ['Auth', 'Bearer API key (per team)'],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between text-xs">
                <span className="text-gray-500 font-medium">{k}</span>
                <span className="font-mono text-gray-800">{v}</span>
              </div>
            ))}
          </div>
        </Section>

        <Section title="Authentication">
          <p className="text-sm text-gray-600 mb-3">
            Each team has a unique API key shown once at creation time. Pass it as a Bearer token
            in every request:
          </p>
          <CodeBlock id="auth-header" code={`Authorization: Bearer <YOUR_API_KEY>`} />
          <p className="text-xs text-gray-500 mt-2">
            API keys are managed in the <strong>Teams</strong> section of the admin console.
            A disabled team's key is rejected with <code className="bg-gray-100 px-1 rounded">401</code>.
          </p>
        </Section>
      </div>

      {/* Right: quick start */}
      <div className="space-y-4">
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
            <span className="text-sm font-medium text-gray-800">Quick Start</span>
            <div className="flex gap-1">
              {(['curl', 'python', 'js'] as const).map(l => (
                <button key={l} onClick={() => setLang(l)}
                  className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${lang === l ? 'bg-indigo-600 text-white' : 'text-gray-500 hover:bg-gray-100'}`}>
                  {l === 'js' ? 'Node.js' : l}
                </button>
              ))}
            </div>
          </div>
          <div className="p-4">
            <CodeBlock id={`qs-${lang}`} code={examples[lang]} lang={lang === 'python' ? 'python' : lang === 'js' ? 'javascript' : 'bash'} />
          </div>
        </div>

        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-100">
            <span className="text-sm font-medium text-gray-800">Example Response</span>
          </div>
          <div className="p-4">
            <CodeBlock id="example-response" lang="json" code={`{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "model": "llama3.2",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "YourOrg savings accounts currently offer..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 28,
    "completion_tokens": 64,
    "total_tokens": 92
  }
}`} />
          </div>
        </div>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// REFERENCE TAB
// ══════════════════════════════════════════════════════════════════════════════
function ReferenceTab() {
  return (
    <div className="max-w-3xl space-y-6">
      <Section title="Endpoints">
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <div className="flex items-center gap-3 px-4 py-3 bg-gray-50 border-b border-gray-200">
            <Badge color="bg-blue-100 text-blue-700">POST</Badge>
            <span className="font-mono text-sm text-gray-800">/v1/chat/completions</span>
            <span className="ml-auto text-xs text-gray-500">OpenAI-compatible</span>
          </div>
          <div className="p-4 text-sm text-gray-600">
            The only client-facing endpoint. Accepts a chat message array and returns a model
            completion after passing through the full gateway pipeline.
          </div>
        </div>
        <div className="mt-2 bg-white border border-gray-200 rounded-lg overflow-hidden">
          <div className="flex items-center gap-3 px-4 py-3 bg-gray-50 border-b border-gray-200">
            <Badge color="bg-green-100 text-green-700">GET</Badge>
            <span className="font-mono text-sm text-gray-800">/</span>
            <span className="ml-auto text-xs text-gray-500">Health check</span>
          </div>
          <div className="p-4 text-sm text-gray-600">
            Returns <code className="bg-gray-100 px-1 rounded">{`{"status":"ok"}`}</code>. Use for uptime monitoring.
          </div>
        </div>
      </Section>

      <Section title="Request Body — POST /v1/chat/completions">
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-2 font-medium text-gray-600 text-xs">Field</th>
                <th className="text-left px-4 py-2 font-medium text-gray-600 text-xs">Type</th>
                <th className="text-left px-4 py-2 font-medium text-gray-600 text-xs">Description</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 px-4">
              <tr className="px-4"><td className="px-4"><ParamRow name="messages" type="array" required desc="Array of message objects. Each has role ('user' | 'assistant') and content (string). System messages are stripped and replaced by the team's configured system prompt." /></td></tr>
              <tr className="px-4"><td className="px-4"><ParamRow name="model" type="string" desc="Model name to use. If omitted, falls back to the team's configured default model." /></td></tr>
              <tr className="px-4"><td className="px-4"><ParamRow name="temperature" type="float" desc="Sampling temperature 0–2. Default: 0.7. Lower = more deterministic." /></td></tr>
              <tr className="px-4"><td className="px-4"><ParamRow name="max_tokens" type="integer" desc="Maximum tokens in the completion. If omitted, the model decides." /></td></tr>
              <tr className="px-4"><td className="px-4"><ParamRow name="stream" type="boolean" desc="Set true for Server-Sent Events streaming. Default: false." /></td></tr>
            </tbody>
          </table>
        </div>
        <p className="text-xs text-red-500 mt-1">* required</p>
      </Section>

      <Section title="Message Object">
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-2 font-medium text-gray-600 text-xs">Field</th>
                <th className="text-left px-4 py-2 font-medium text-gray-600 text-xs">Type</th>
                <th className="text-left px-4 py-2 font-medium text-gray-600 text-xs">Description</th>
              </tr>
            </thead>
            <tbody className="px-4">
              <tr><td className="px-4"><ParamRow name="role" type="string" required desc='"user" or "assistant". Do not send "system" — it will be stripped.' /></td></tr>
              <tr><td className="px-4"><ParamRow name="content" type="string" required desc="The message text." /></td></tr>
            </tbody>
          </table>
        </div>
      </Section>

      <Section title="Error Responses">
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-2 font-medium text-gray-600 text-xs">Status</th>
                <th className="text-left px-4 py-2 font-medium text-gray-600 text-xs">Reason</th>
                <th className="text-left px-4 py-2 font-medium text-gray-600 text-xs">Detail</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {[
                ['401', 'bg-red-100 text-red-700', 'Unauthorized', 'Missing, invalid, or disabled API key.'],
                ['400', 'bg-orange-100 text-orange-700', 'DLP Blocked — Request', 'User message matched a DLP pattern. incident_id returned.'],
                ['429', 'bg-yellow-100 text-yellow-700', 'Rate Limited', 'Team exceeded its request quota. Check retry_after in response.'],
                ['502', 'bg-orange-100 text-orange-700', 'DLP Blocked — Response', 'Model reply matched a DLP pattern. incident_id returned.'],
                ['502', 'bg-red-100 text-red-700', 'Model Error', 'Ollama/vLLM returned a 5xx or is unreachable.'],
                ['504', 'bg-red-100 text-red-700', 'Timeout', 'Model did not respond within the configured timeout.'],
              ].map(([status, badge, reason, detail], i) => (
                <tr key={i} className="hover:bg-gray-50">
                  <td className="px-4 py-2.5"><Badge color={badge}>{status}</Badge></td>
                  <td className="px-4 py-2.5 text-xs font-medium text-gray-700">{reason}</td>
                  <td className="px-4 py-2.5 text-xs text-gray-500">{detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section title="DLP Block Response Body">
        <CodeBlock id="dlp-err" lang="json" code={`{
  "detail": {
    "error": "Request blocked by DLP policy",
    "incident_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "findings": [
      { "pattern": "cnic", "severity": "Critical" },
      { "pattern": "credit_card", "severity": "Critical" }
    ]
  }
}`} />
      </Section>

      <Section title="Rate Limit Response Body">
        <CodeBlock id="rate-err" lang="json" code={`{
  "detail": {
    "error": "Rate limit exceeded",
    "team": "HR Assistant",
    "limit": 10,
    "window_sec": 60,
    "retry_after": 43
  }
}`} />
      </Section>

      <Section title="Streaming (SSE)">
        <p className="text-sm text-gray-600 mb-3">
          Set <code className="bg-gray-100 px-1 rounded">"stream": true</code> to receive Server-Sent Events.
          Each event is a JSON delta following the OpenAI streaming format.
        </p>
        <CodeBlock id="stream-ex" lang="bash" code={`curl -X POST ${BASE}/v1/chat/completions \\
  -H "Authorization: Bearer <YOUR_API_KEY>" \\
  -H "Content-Type: application/json" \\
  -d '{"model":"llama3.2","messages":[{"role":"user","content":"Hello"}],"stream":true}'

# Response stream:
data: {"choices":[{"delta":{"role":"assistant"},"index":0}]}
data: {"choices":[{"delta":{"content":"Hello"},"index":0}]}
data: {"choices":[{"delta":{"content":"!"},"index":0}]}
data: [DONE]`} />
      </Section>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// SANDBOX TAB
// ══════════════════════════════════════════════════════════════════════════════
function SandboxTab({ isAuthenticated }: { isAuthenticated: boolean }) {
  if (!isAuthenticated) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <div className="w-14 h-14 bg-indigo-100 rounded-full flex items-center justify-center mb-4">
          <LogIn className="w-6 h-6 text-indigo-600" />
        </div>
        <h3 className="text-base font-semibold text-gray-900 mb-1">Sign in to use the sandbox</h3>
        <p className="text-sm text-gray-500 mb-5 max-w-sm">
          The live sandbox sends real requests through the gateway. You need to be logged in to access it.
        </p>
        <Link
          to="/login"
          className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-5 py-2.5 rounded transition-colors"
        >
          <LogIn className="w-4 h-4" /> Sign in to Admin Console
        </Link>
        <p className="text-xs text-gray-400 mt-4">
          The Overview and Endpoint Reference tabs are always accessible.
        </p>
      </div>
    );
  }
  const [apiKey, setApiKey] = useState('');
  const [model, setModel] = useState('llama3.2');
  const [temperature, setTemperature] = useState(0.7);
  const [maxTokens, setMaxTokens] = useState<number | ''>('');
  const [messages, setMessages] = useState([{ role: 'user', content: '' }]);
  const [lang, setLang] = useState<'curl' | 'python' | 'js'>('curl');
  const [streamMode, setStreamMode] = useState(true);                  // stream toggle
  const [loading, setLoading] = useState(false);
  const [streamText, setStreamText] = useState<string | null>(null);   // streaming reply
  const [errorMsg, setErrorMsg]     = useState<string | null>(null);
  const [httpStatus, setHttpStatus] = useState<number | null>(null);
  const [showReq, setShowReq] = useState(true);
  const responseRef = useRef<HTMLDivElement>(null);
  const abortRef    = useRef<AbortController | null>(null);

  const lastUserMsg = messages.filter(m => m.role === 'user').slice(-1)[0]?.content || '';

  const codeMap = {
    curl: makeCurl(apiKey, model, lastUserMsg, temperature, maxTokens),
    python: makePython(apiKey, model, lastUserMsg, temperature, maxTokens),
    js: makeJs(apiKey, model, lastUserMsg, temperature, maxTokens),
  };

  const addMessage = () => setMessages(m => [...m, { role: 'user', content: '' }]);
  const removeMessage = (i: number) => setMessages(m => m.filter((_, idx) => idx !== i));
  const updateMessage = (i: number, field: 'role' | 'content', val: string) =>
    setMessages(m => m.map((msg, idx) => idx === i ? { ...msg, [field]: val } : msg));

  const run = async () => {
    if (!apiKey) { alert('Enter your API key first.'); return; }
    if (!messages.some(m => m.content.trim())) { alert('Add at least one message with content.'); return; }

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setStreamText('');
    setErrorMsg(null);
    setHttpStatus(null);

    setTimeout(() => responseRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);

    try {
      const body: Record<string, unknown> = { model, messages, temperature, stream: streamMode };
      if (maxTokens !== '') body.max_tokens = maxTokens;

      const res = await fetch(`${BASE}/v1/chat/completions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${apiKey}` },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      setHttpStatus(res.status);

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({ detail: res.statusText }));
        const msg = typeof errJson?.detail === 'string'
          ? errJson.detail
          : JSON.stringify(errJson?.detail ?? errJson);
        setErrorMsg(msg);
        setLoading(false);
        return;
      }

      if (streamMode) {
        // Read SSE stream — tokens appear as generated
        const reader = res.body!.getReader();
        const decoder = new TextDecoder();
        let buf = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });

          // SSE lines: "data: {...}\n\n"
          const lines = buf.split('\n');
          buf = lines.pop() ?? '';          // keep incomplete last line

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed.startsWith('data:')) continue;
            const payload = trimmed.slice(5).trim();
            if (payload === '[DONE]') break;
            try {
              const chunk = JSON.parse(payload);
              // Synthetic error event from gateway (e.g. invalid model name)
              if (chunk.error) {
                setErrorMsg(chunk.error);
                setHttpStatus(chunk.status ?? 502);
                setStreamText(null);
                reader.cancel();
                break;
              }
              const delta = chunk?.choices?.[0]?.delta?.content;
              if (delta) setStreamText(t => (t ?? '') + delta);
            } catch { /* ignore malformed chunks */ }
          }
        }
      } else {
        // Non-streaming — wait for full JSON response
        const json = await res.json().catch(() => null);
        const content = json?.choices?.[0]?.message?.content ?? null;
        setStreamText(content ?? '(empty response)');
      }
    } catch (e: unknown) {
      if ((e as { name?: string })?.name !== 'AbortError') {
        setErrorMsg('Network error — is the backend running?');
        setHttpStatus(0);
      }
    } finally {
      setLoading(false);
    }
  };

  const stop = () => {
    abortRef.current?.abort();
    setLoading(false);
  };

  return (
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
      {/* Left: builder */}
      <div className="space-y-4">
        <div className="bg-white border border-gray-200 rounded-lg p-5 space-y-4">
          <h3 className="font-semibold text-gray-900 text-sm">Request Builder</h3>

          {/* API Key */}
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              API Key <span className="text-red-500">*</span>
            </label>
            <input
              type="password"
              value={apiKey}
              onChange={e => setApiKey(e.target.value)}
              placeholder="Paste your team API key"
              className="w-full px-3 py-2 border border-gray-300 rounded text-sm font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <p className="text-xs text-gray-400 mt-1">Find this in Teams → Add Team (shown once at creation)</p>
          </div>

          {/* Model */}
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Model</label>
            <input
              value={model}
              onChange={e => setModel(e.target.value)}
              placeholder="e.g. llama3.2"
              className="w-full px-3 py-2 border border-gray-300 rounded text-sm font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          {/* Messages */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-medium text-gray-700">Messages</label>
              <button onClick={addMessage} className="text-xs text-indigo-600 hover:underline font-medium">+ Add message</button>
            </div>
            <div className="space-y-2">
              {messages.map((msg, i) => (
                <div key={i} className="border border-gray-200 rounded overflow-hidden">
                  <div className="flex items-center bg-gray-50 border-b border-gray-200 px-2 py-1 gap-2">
                    <select
                      value={msg.role}
                      onChange={e => updateMessage(i, 'role', e.target.value)}
                      className="text-xs border-0 bg-transparent font-medium text-gray-700 focus:outline-none cursor-pointer"
                    >
                      <option value="user">user</option>
                      <option value="assistant">assistant</option>
                    </select>
                    {messages.length > 1 && (
                      <button onClick={() => removeMessage(i)} className="ml-auto text-gray-400 hover:text-red-500 text-xs">✕</button>
                    )}
                  </div>
                  <textarea
                    rows={3}
                    value={msg.content}
                    onChange={e => updateMessage(i, 'content', e.target.value)}
                    placeholder={msg.role === 'user' ? 'What is your question?' : 'Assistant reply...'}
                    className="w-full px-3 py-2 text-sm resize-none focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  />
                </div>
              ))}
            </div>
          </div>

          {/* Params */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Temperature <span className="text-gray-400 font-normal">{temperature}</span>
              </label>
              <input
                type="range" min={0} max={2} step={0.1} value={temperature}
                onChange={e => setTemperature(parseFloat(e.target.value))}
                className="w-full accent-indigo-600"
              />
              <div className="flex justify-between text-xs text-gray-400 mt-0.5">
                <span>0 precise</span><span>2 creative</span>
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Max Tokens <span className="text-gray-400 font-normal">(optional)</span></label>
              <input
                type="number" min={1} value={maxTokens}
                onChange={e => setMaxTokens(e.target.value === '' ? '' : parseInt(e.target.value))}
                placeholder="default"
                className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          </div>

          {/* Stream toggle */}
          <div className="flex items-center justify-between py-2 px-3 bg-gray-50 rounded-lg border border-gray-200">
            <div>
              <p className="text-xs font-medium text-gray-700">Streaming</p>
              <p className="text-xs text-gray-400 mt-0.5">
                {streamMode ? 'Tokens appear as generated (SSE)' : 'Wait for complete response (JSON)'}
              </p>
            </div>
            <button
              onClick={() => setStreamMode(v => !v)}
              className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none ${streamMode ? 'bg-emerald-500' : 'bg-gray-300'}`}
            >
              <span className={`w-3.5 h-3.5 bg-white rounded-full shadow transition-transform ${streamMode ? 'translate-x-4' : 'translate-x-1'}`} />
            </button>
          </div>

          <div className="flex gap-2">
            <button
              onClick={run}
              disabled={loading || !apiKey}
              className="flex-1 flex items-center justify-center gap-2 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded disabled:opacity-50 transition-colors"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
              {loading ? (streamMode ? 'Streaming…' : 'Waiting…') : 'Send Request'}
            </button>
            {loading && (
              <button
                onClick={stop}
                className="px-4 py-2.5 border border-gray-300 text-gray-700 text-sm font-medium rounded hover:bg-gray-50 transition-colors"
              >
                Stop
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Right: code + response */}
      <div className="space-y-4">
        {/* Generated code */}
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
            <button
              onClick={() => setShowReq(v => !v)}
              className="flex items-center gap-1.5 text-sm font-medium text-gray-800"
            >
              {showReq ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              Generated Request
            </button>
            <div className="flex gap-1">
              {(['curl', 'python', 'js'] as const).map(l => (
                <button key={l} onClick={() => setLang(l)}
                  className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${lang === l ? 'bg-indigo-600 text-white' : 'text-gray-500 hover:bg-gray-100'}`}>
                  {l === 'js' ? 'Node.js' : l}
                </button>
              ))}
            </div>
          </div>
          {showReq && (
            <div className="p-4">
              <CodeBlock id={`sandbox-${lang}`} code={codeMap[lang]} lang={lang === 'python' ? 'python' : lang === 'js' ? 'javascript' : 'bash'} />
            </div>
          )}
        </div>

        {/* Response */}
        <div ref={responseRef} className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-100 flex items-center gap-3">
            <span className="text-sm font-medium text-gray-800">Response</span>
            {httpStatus !== null && (
              <Badge color={httpStatus >= 200 && httpStatus < 300 ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}>
                {httpStatus === 0 ? 'Network Error' : `HTTP ${httpStatus}`}
              </Badge>
            )}
            {loading && streamMode && (
              <span className="flex items-center gap-1 text-xs text-indigo-600">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-indigo-600 animate-pulse" />
                streaming
              </span>
            )}
          </div>
          <div className="p-4">
            {streamText === null && !loading && !errorMsg && (
              <p className="text-sm text-gray-400 text-center py-6">Response will appear here after you send a request.</p>
            )}
            {errorMsg && (
              <div className="flex items-start gap-2 bg-red-50 border border-red-200 rounded p-3">
                <AlertTriangle className="w-4 h-4 text-red-500 mt-0.5 shrink-0" />
                <p className="text-sm text-red-700">{errorMsg}</p>
              </div>
            )}
            {(streamText !== null && !errorMsg) && (
              <div className="bg-green-50 border border-green-200 rounded p-3 min-h-[60px]">
                <p className="text-xs font-medium text-green-700 mb-1">Assistant Reply</p>
                <p className="text-sm text-gray-800 whitespace-pre-wrap">
                  {streamText}
                  {loading && <span className="inline-block w-0.5 h-4 bg-gray-600 ml-0.5 animate-pulse align-middle" />}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
