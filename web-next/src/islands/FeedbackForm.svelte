<script lang="ts">
  interface Props {
    entityId: number;
    entityName: string;
  }
  let { entityId, entityName }: Props = $props();

  let open = $state(false);
  let sending = $state(false);
  let success = $state<string | null>(null);
  let error = $state<string | null>(null);

  let issueType = $state<string>('wrong_fact');
  let field = $state<string>('');
  let message = $state<string>('');
  let email = $state<string>('');

  const TYPES = [
    { v: 'wrong_fact', l: 'Factual error' },
    { v: 'missing_source', l: 'Missing citation' },
    { v: 'wrong_relationship', l: 'Wrong relationship' },
    { v: 'missing_relationship', l: 'Missing relationship' },
    { v: 'misattribution', l: 'Wrong tradition' },
    { v: 'ethics', l: 'Ethical concern' },
    { v: 'typo', l: 'Typo / spelling' },
    { v: 'other', l: 'Other' },
  ];

  async function submit(ev: Event) {
    ev.preventDefault();
    if (message.trim().length < 10) {
      error = 'Please include at least a short explanation (10+ chars).';
      return;
    }
    sending = true;
    error = null;
    try {
      const resp = await fetch('/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          entity_id: entityId,
          field: field.trim() || null,
          issue_type: issueType,
          message: message.trim(),
          reporter_email: email.trim() || null,
        }),
      });
      if (resp.status === 429) {
        error = 'Rate-limited — please try again later.';
        return;
      }
      if (!resp.ok) {
        error = `Server error: ${resp.status}`;
        return;
      }
      const payload = await resp.json();
      success = payload?.data?.status === 'duplicate'
        ? 'Already received — thanks!'
        : 'Thanks — report received.';
      message = '';
      field = '';
      setTimeout(() => { open = false; success = null; }, 2200);
    } catch (e) {
      error = (e as Error).message;
    } finally {
      sending = false;
    }
  }
</script>

<button class="fb-trigger ui" onclick={() => open = !open} aria-label="Report an issue">
  {open ? 'Close report' : 'Report an issue'}
</button>

{#if open}
  <form class="fb-form" onsubmit={submit} aria-label="Report an issue with {entityName}">
    <div class="row">
      <label>
        Issue
        <select bind:value={issueType}>
          {#each TYPES as t}<option value={t.v}>{t.l}</option>{/each}
        </select>
      </label>
      <label>
        Field (optional)
        <input type="text" bind:value={field} placeholder="e.g. alignment, parents" maxlength="100" />
      </label>
    </div>
    <label>
      Details
      <textarea bind:value={message}
                placeholder="What is wrong, and what would be correct? Link to a source if possible."
                maxlength="4000" rows="4"></textarea>
    </label>
    <label>
      Email (optional — for follow-up only)
      <input type="email" bind:value={email} placeholder="you@example.org" maxlength="200" />
    </label>

    <div class="actions">
      <button type="submit" disabled={sending}>{sending ? 'Sending…' : 'Send report'}</button>
      {#if success}<span class="ok">{success}</span>{/if}
      {#if error}<span class="err">{error}</span>{/if}
    </div>

    <p class="privacy ui">
      We hash your IP to catch duplicates and never store the raw address. Email is optional and used only to ask you a clarifying question.
    </p>
  </form>
{/if}

<style>
  .fb-trigger {
    padding: 6px 12px;
    border: 1px solid var(--rule);
    background: transparent;
    color: var(--ink-dim);
    font-size: var(--fs-sm);
    border-radius: var(--r-sm);
    cursor: pointer;
    font-family: inherit;
  }
  .fb-trigger:hover { color: var(--accent); border-color: var(--accent); }
  .fb-form {
    width: 100%;
    max-width: 640px;
    margin-top: var(--sp-3);
    padding: var(--sp-4);
    border: 1px solid var(--rule);
    border-radius: var(--r-md);
    background: var(--bg-alt);
    display: grid;
    gap: var(--sp-3);
    font-size: var(--fs-sm);
  }
  .fb-form label {
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-family: var(--font-sans);
    font-size: var(--fs-xs);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--ink-faint);
  }
  .fb-form select,
  .fb-form input,
  .fb-form textarea {
    font-family: var(--font-serif);
    font-size: var(--fs-sm);
    background: var(--bg);
    border: 1px solid var(--rule);
    border-radius: var(--r-sm);
    padding: 6px 8px;
    color: var(--ink);
    text-transform: none;
    letter-spacing: normal;
  }
  .fb-form textarea { resize: vertical; }
  .row {
    display: grid;
    grid-template-columns: minmax(140px, 1fr) 2fr;
    gap: var(--sp-3);
  }
  .actions {
    display: flex;
    gap: var(--sp-3);
    align-items: center;
    flex-wrap: wrap;
  }
  .actions button {
    padding: 6px 14px;
    border: 1px solid var(--accent);
    background: var(--accent);
    color: var(--bg);
    border-radius: var(--r-sm);
    cursor: pointer;
    font-size: var(--fs-sm);
  }
  .actions button:hover { background: transparent; color: var(--accent); }
  .actions button:disabled { opacity: 0.5; cursor: not-allowed; }
  .ok { color: var(--conf-high); font-size: var(--fs-sm); }
  .err { color: var(--conf-low); font-size: var(--fs-sm); }
  .privacy {
    font-size: var(--fs-xs);
    color: var(--ink-faint);
    margin: 0;
  }
</style>
