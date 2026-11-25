import { json } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import { PollyClient, SynthesizeSpeechCommand } from '@aws-sdk/client-polly';
import type { RequestHandler } from './$types';

const DEFAULT_AWS_REGION = 'us-east-1';
const DEFAULT_VOICE_ID = 'Amy';

export const POST: RequestHandler = async ({ request }) => {
  const { text } = (await request.json()) as { text?: string };
  if (!text || !text.trim()) {
    return new Response(null, { status: 204 });
  }

  try {
    const client = new PollyClient({ region: env.AWS_REGION || DEFAULT_AWS_REGION });
    const command = new SynthesizeSpeechCommand({
      Text: text,
      OutputFormat: 'mp3',
      VoiceId: (env.POLLY_VOICE_ID || DEFAULT_VOICE_ID) as never,
      Engine: 'neural'
    });

    const result = await client.send(command);
    const bytes = await result.AudioStream?.transformToByteArray();
    if (!bytes) {
      return json({ error: 'No audio returned from Polly' }, { status: 502 });
    }
    return new Response(Buffer.from(bytes), { headers: { 'Content-Type': 'audio/mpeg' } });
  } catch (error) {
    return json(
      { error: error instanceof Error ? error.message : 'Speech synthesis failed' },
      { status: 502 }
    );
  }
};
