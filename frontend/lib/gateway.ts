import { getAuditStore } from '@/lib/audit-store';
import { bedrockChat, bedrockConfigured } from '@/lib/bedrock';

const gatewayUrl = () => (process.env.TRUEFOUNDRY_GATEWAY_URL ?? '').replace(/\/$/, '');
const apiKey = () => process.env.TRUEFOUNDRY_API_KEY ?? '';

const MODEL_ALIASES: Record<string, string> = {
  'qwen-max': process.env.QWEN_MODEL_ID ?? 'qwen/qwen3-32b',
};

export type GatewayMetadata = {
  case_id?: string;
  turn?: number;
  caller_id?: string;
};

export function gatewayConfigured(): boolean {
  return Boolean(gatewayUrl() && apiKey());
}

export function llmConfigured(): boolean {
  return gatewayConfigured() || bedrockConfigured();
}

function resolveModel(modelId: string): string {
  return MODEL_ALIASES[modelId] ?? modelId;
}

function metadataHeader(metadata?: GatewayMetadata): Record<string, string> {
  if (!metadata) return {};
  const payload = Object.fromEntries(
    Object.entries({
      case_id: metadata.case_id,
      turn: metadata.turn?.toString(),
      caller_id: metadata.caller_id,
      application: 'caseflow',
    }).filter(([, v]) => v)
  );
  return { 'X-TFY-METADATA': JSON.stringify(payload) };
}

async function truefoundryChat(
  modelId: string,
  messages: Array<{ role: 'system' | 'user' | 'assistant'; content: string }>,
  options?: { temperature?: number; metadata?: GatewayMetadata }
): Promise<{ content: string; model: string; provider: 'truefoundry'; latencyMs: number }> {
  const base = gatewayUrl();
  if (!base || !apiKey()) {
    throw new Error('TrueFoundry gateway is not configured');
  }

  const started = Date.now();
  const paths = [`${base}/openai/chat/completions`, `${base}/v1/chat/completions`];
  let lastError: Error | null = null;

  for (const path of paths) {
    try {
      const res = await fetch(path, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${apiKey()}`,
          'X-TFY-LOGGING-CONFIG': '{"enabled": true}',
          'x-tfy-request-timeout': '8000',
          ...metadataHeader(options?.metadata),
        },
        body: JSON.stringify({
          model: resolveModel(modelId),
          messages,
          temperature: options?.temperature ?? 0.2,
        }),
      });

      if (!res.ok) {
        throw new Error(`Gateway error ${res.status}`);
      }

      const data = (await res.json()) as {
        choices?: Array<{ message?: { content?: string } }>;
      };
      const content = data.choices?.[0]?.message?.content ?? '';
      return {
        content,
        model: resolveModel(modelId),
        provider: 'truefoundry',
        latencyMs: Date.now() - started,
      };
    } catch (err) {
      lastError = err instanceof Error ? err : new Error(String(err));
    }
  }

  throw lastError ?? new Error('Gateway chat failed');
}

export async function gatewayChat(
  modelId: string,
  messages: Array<{ role: 'system' | 'user' | 'assistant'; content: string }>,
  options?: { temperature?: number; metadata?: GatewayMetadata }
): Promise<{
  content: string;
  model: string;
  latencyMs: number;
  provider: string;
  failover: boolean;
}> {
  const started = Date.now();
  const providers: Array<'truefoundry' | 'bedrock'> = [];
  if (gatewayConfigured()) providers.push('truefoundry');
  if (bedrockConfigured()) providers.push('bedrock');

  if (!providers.length) {
    throw new Error('No LLM configured (TrueFoundry or Bedrock)');
  }

  let lastError: Error | null = null;
  for (let index = 0; index < providers.length; index += 1) {
    const provider = providers[index];
    try {
      const result =
        provider === 'truefoundry'
          ? await truefoundryChat(modelId, messages, options)
          : {
              ...(await bedrockChat(messages, { temperature: options?.temperature })),
              latencyMs: Date.now() - started,
            };

      getAuditStore().append({
        event_type: 'gateway_call',
        model_id: modelId,
        resolved_model: result.model,
        provider: result.provider,
        input_chars: messages.reduce((n, m) => n + m.content.length, 0),
        output_chars: result.content.length,
        latency_ms: result.latencyMs,
        failover: index > 0,
        failover_reason: lastError?.message ?? null,
        ...options?.metadata,
      });

      return {
        content: result.content,
        model: result.model,
        latencyMs: result.latencyMs,
        provider: result.provider,
        failover: index > 0,
      };
    } catch (err) {
      lastError = err instanceof Error ? err : new Error(String(err));
    }
  }

  throw lastError ?? new Error('Gateway chat failed');
}
