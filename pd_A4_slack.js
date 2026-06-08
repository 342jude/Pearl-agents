// PIPEDREAM STEP 4 — "notify"  (Node.js code step)
// Posts a digest of what just went live to your Slack channel via an Incoming Webhook.
// Env var: SLACK_WEBHOOK_URL  (created in Slack -> Incoming Webhooks for the #news-desk channel).
export default defineComponent({
  async run({ steps, $ }) {
    const posted = steps.route_write.$return_value;
    if (!posted || !posted.length) return $.flow.exit("nothing posted");

    const dot = { hot: "🔴", normal: "🔵", low: "🟡" };
    const lines = posted.map(p =>
      `${dot[p.importance] || "🔵"} *#${p.id}*  ${p.headline}   _(${p.source})_`
    );
    const text = `*Pearl News Desk — ${posted.length} posted to the Calendar*\n` +
      lines.join("\n") +
      `\n\nReply in-thread:  \`remove #id\`  ·  \`rewrite #id: your text\`  ·  \`replace #id\`  ·  \`alt #id\``;

    await fetch(process.env.SLACK_WEBHOOK_URL, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ text })
    });
    return `notified ${posted.length}`;
  }
});
