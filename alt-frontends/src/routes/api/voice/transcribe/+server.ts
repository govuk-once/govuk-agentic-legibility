import { json } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import {
  StartStreamTranscriptionCommand,
  TranscribeStreamingClient
} from '@aws-sdk/client-transcribe-streaming';
import type { RequestHandler } from './$types';

const DEFAULT_AWS_REGION = 'us-east-1';
const DEFAULT_LANGUAGE_CODE = 'en-GB';
const SAMPLE_RATE_HZ = 16000;
const CHUNK_BYTES = 6400; // ~200ms of 16-bit mono PCM at 16kHz

// Feeds a full utterance buffer to AWS Transcribe's *streaming* API as a
// software-chunked async generator, so the frontend gets near-real-time
// turnaround without the project needing S3-based batch jobs or a live
// browser<->server audio stream (the project deliberately dropped
// WebSockets — see the deleted src/lib/api/ws.ts).
async function* audioStream(buffer: Buffer) {
  for (let offset = 0; offset < buffer.length; offset += CHUNK_BYTES) {
    yield { AudioEvent: { AudioChunk: buffer.subarray(offset, offset + CHUNK_BYTES) } };
  }
}

export const POST: RequestHandler = async ({ request }) => {
  const arrayBuffer = await request.arrayBuffer();
  const buffer = Buffer.from(arrayBuffer);
  if (buffer.length === 0) {
    return json({ transcript: '' });
  }

  try {
    const client = new TranscribeStreamingClient({ region: env.AWS_REGION || DEFAULT_AWS_REGION });
    const command = new StartStreamTranscriptionCommand({
      LanguageCode: (env.TRANSCRIBE_LANGUAGE_CODE || DEFAULT_LANGUAGE_CODE) as never,
      MediaEncoding: 'pcm',
      MediaSampleRateHertz: SAMPLE_RATE_HZ,
      AudioStream: audioStream(buffer)
    });

    const response = await client.send(command);
    let transcript = '';
    for await (const event of response.TranscriptResultStream ?? []) {
      const results = event.TranscriptEvent?.Transcript?.Results ?? [];
      for (const result of results) {
        if (result.IsPartial) continue;
        const alternative = result.Alternatives?.[0]?.Transcript;
        if (alternative) {
          transcript += (transcript ? ' ' : '') + alternative;
        }
      }
    }
    return json({ transcript: transcript.trim() });
  } catch (error) {
    return json(
      { error: error instanceof Error ? error.message : 'Transcription failed' },
      { status: 502 }
    );
  }
};
