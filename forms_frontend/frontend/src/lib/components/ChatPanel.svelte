<script lang="ts">
  import { sendChat } from "../api";

  interface Props {
    sessionId: string;
    preloadedConversation?: Array<{ role: string; content: string }>;
    onStateChange: () => void;
  }

  let { sessionId, preloadedConversation = [], onStateChange }: Props = $props();

  interface ChatMessage {
    role: "user" | "assistant";
    text: string;
    preloaded?: boolean;
  }

  let messages: ChatMessage[] = $state([]);
  let inputText = $state("");
  let sending = $state(false);
  let messagesContainer: HTMLDivElement | undefined = $state();

  $effect(() => {
    const initial: ChatMessage[] = [];

    if (preloadedConversation.length > 0) {
      for (const msg of preloadedConversation) {
        initial.push({
          role: msg.role as "user" | "assistant",
          text: msg.content,
          preloaded: true,
        });
      }
      initial.push({
        role: "assistant",
        text: "I have context from our earlier conversation. I'll use it to help with the form.",
      });
    } else {
      initial.push({
        role: "assistant",
        text: "Hello. I can help you complete this form. Tell me about your situation, or ask me questions about any of the form fields.",
      });
    }

    messages = initial;
  });

  function scrollToBottom() {
    if (messagesContainer) {
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
  }

  async function handleSend() {
    const text = inputText.trim();
    if (!text || sending) return;

    messages = [...messages, { role: "user", text }];
    inputText = "";
    sending = true;

    try {
      const result = await sendChat(sessionId, text);
      messages = [...messages, { role: "assistant", text: result.response }];
      onStateChange();
    } catch (e: any) {
      messages = [
        ...messages,
        {
          role: "assistant",
          text: `Sorry, something went wrong: ${e.message}`,
        },
      ];
    } finally {
      sending = false;
      setTimeout(scrollToBottom, 50);
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }
</script>

<div class="chat-panel">
  <h2 class="govuk-heading-m">AI assistance</h2>
  {#if preloadedConversation.length > 0}
    <p class="govuk-body-s govuk-!-margin-bottom-2">
      <strong class="govuk-tag govuk-tag--blue" style="font-size: 12px;">Conversation loaded</strong>
      The assistant has context from a previous conversation ({preloadedConversation.length} messages).
    </p>
  {:else}
    <p class="govuk-body-s govuk-!-margin-bottom-2">
      Describe your situation and the assistant can help fill in the form.
    </p>
  {/if}

  <div class="chat-messages" bind:this={messagesContainer}>
    {#each messages as msg}
      <div
        class="chat-message chat-message--{msg.role}"
        class:chat-message--preloaded={msg.preloaded}
      >
        <strong class="govuk-body-s" style="display: block; margin-bottom: 4px;">
          {msg.role === "user" ? "You" : "Assistant"}
          {#if msg.preloaded}
            <span style="color: #505a5f; font-weight: normal;"> (earlier)</span>
          {/if}
        </strong>
        <span class="govuk-body-s">{msg.text}</span>
      </div>
    {/each}
    {#if sending}
      <div class="chat-message chat-message--assistant">
        <span class="govuk-body-s" style="color: #626a6e;">Thinking...</span>
      </div>
    {/if}
  </div>

  <div class="chat-input-row">
    <textarea
      class="govuk-textarea govuk-!-margin-bottom-0"
      rows="2"
      bind:value={inputText}
      onkeydown={handleKeydown}
      placeholder="Type a message..."
      disabled={sending}
      aria-label="Chat message"
    ></textarea>
    <button
      class="govuk-button govuk-button--secondary"
      onclick={handleSend}
      disabled={sending || !inputText.trim()}
      style="align-self: flex-end;"
    >
      Send
    </button>
  </div>
</div>
