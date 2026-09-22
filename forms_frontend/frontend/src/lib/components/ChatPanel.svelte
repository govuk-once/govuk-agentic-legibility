<script lang="ts">
  import { sendChat } from "../api";

  interface Props {
    sessionId: string;
    onStateChange: () => void;
  }

  let { sessionId, onStateChange }: Props = $props();

  interface ChatMessage {
    role: "user" | "assistant";
    text: string;
  }

  let messages: ChatMessage[] = $state([
    {
      role: "assistant",
      text: "Hello. I can help you complete this form. Tell me about your situation, or ask me questions about any of the form fields.",
    },
  ]);
  let inputText = $state("");
  let sending = $state(false);
  let messagesContainer: HTMLDivElement | undefined = $state();

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
  <p class="govuk-body-s govuk-!-margin-bottom-2">
    Describe your situation and the assistant can help fill in the form.
  </p>

  <div class="chat-messages" bind:this={messagesContainer}>
    {#each messages as msg}
      <div class="chat-message chat-message--{msg.role}">
        <strong class="govuk-body-s" style="display: block; margin-bottom: 4px;">
          {msg.role === "user" ? "You" : "Assistant"}
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
