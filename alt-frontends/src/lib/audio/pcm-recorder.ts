// Browser-side capture for /voice. Uses the Web Audio API (not
// MediaRecorder) because MediaRecorder's default WebM/Opus container isn't
// one of AWS Transcribe Streaming's supported MediaEncoding values
// (pcm/ogg-opus/flac) — capturing raw PCM sidesteps the container mismatch
// entirely. Recording is push-to-talk/batch (one full buffer per utterance,
// uploaded on stop), consistent with the project's no-WebSockets decision.

const TARGET_SAMPLE_RATE = 16000;

const WORKLET_SOURCE = `
class PcmCaptureProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const channel = inputs[0]?.[0];
    if (channel) {
      this.port.postMessage(channel.slice());
    }
    return true;
  }
}
registerProcessor('pcm-capture-processor', PcmCaptureProcessor);
`;

export interface PcmRecording {
  /** Stops capture and resolves to a 16kHz mono PCM16LE buffer. */
  stop(): Promise<ArrayBuffer>;
}

function floatTo16BitPCM(samples: Float32Array): Int16Array {
  const out = new Int16Array(samples.length);
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return out;
}

function downsample(buffer: Float32Array, inputRate: number, outputRate: number): Float32Array {
  if (outputRate === inputRate) return buffer;
  const ratio = inputRate / outputRate;
  const newLength = Math.round(buffer.length / ratio);
  const result = new Float32Array(newLength);
  let offsetBuffer = 0;
  for (let offsetResult = 0; offsetResult < newLength; offsetResult++) {
    const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio);
    let accum = 0;
    let count = 0;
    for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
      accum += buffer[i];
      count++;
    }
    result[offsetResult] = count > 0 ? accum / count : 0;
    offsetBuffer = nextOffsetBuffer;
  }
  return result;
}

export async function startPcmRecording(): Promise<PcmRecording> {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const audioContext = new AudioContext();

  const workletUrl = URL.createObjectURL(
    new Blob([WORKLET_SOURCE], { type: 'application/javascript' })
  );
  try {
    await audioContext.audioWorklet.addModule(workletUrl);
  } finally {
    URL.revokeObjectURL(workletUrl);
  }

  const source = audioContext.createMediaStreamSource(stream);
  const worklet = new AudioWorkletNode(audioContext, 'pcm-capture-processor');

  const chunks: Float32Array[] = [];
  worklet.port.onmessage = (event: MessageEvent<Float32Array>) => {
    chunks.push(event.data);
  };

  // Deliberately not connected to audioContext.destination — capturing the
  // mic input should not echo it back through the user's speakers.
  source.connect(worklet);

  return {
    async stop(): Promise<ArrayBuffer> {
      source.disconnect();
      worklet.disconnect();
      worklet.port.onmessage = null;
      stream.getTracks().forEach((track) => track.stop());

      const inputRate = audioContext.sampleRate;
      await audioContext.close();

      const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
      const merged = new Float32Array(totalLength);
      let offset = 0;
      for (const chunk of chunks) {
        merged.set(chunk, offset);
        offset += chunk.length;
      }

      const pcm16 = floatTo16BitPCM(downsample(merged, inputRate, TARGET_SAMPLE_RATE));
      return pcm16.buffer as ArrayBuffer;
    }
  };
}
