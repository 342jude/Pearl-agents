// Pearl News Desk — single-process runner for GitHub Actions.
// Wraps the four original Pipedream step files UNCHANGED, emulating Pipedream's `steps` + `$`.
// Each step's return value is fed to the next exactly as Pipedream did (steps.<name>.$return_value).
// Env (from GitHub repo secrets): WP_BASE, WP_USER, WP_APP_PASS, ANTHROPIC_API_KEY, ANTHROPIC_MODEL, SLACK_WEBHOOK_URL.

// Pipedream injects defineComponent as a global; here it just returns the component object.
globalThis.defineComponent = (c) => c;

const steps = {};
// $.flow.exit(msg) ends the workflow in Pipedream; here it throws a sentinel that stops the pipeline cleanly.
const $ = { flow: { exit: (msg) => { const e = new Error(String(msg)); e.__exit = true; throw e; } } };

async function runStep(name, file) {
  const mod = (await import(file)).default;
  try {
    const rv = await mod.run({ steps, $ });
    steps[name] = { $return_value: rv };
    return true;
  } catch (e) {
    if (e && e.__exit) { console.log(`· stopped at ${name}: ${e.message}`); return false; }
    throw e;
  }
}

(async () => {
  console.log("Pearl News Desk — run start", new Date().toISOString());
  if (!(await runStep("fetch_filter", "./pd_A1_fetch_filter.js"))) return;
  if (!(await runStep("haiku",        "./pd_A2_haiku.js")))        return;
  if (!(await runStep("route_write",  "./pd_A3_route_write.js")))  return;
  await runStep("notify", "./pd_A4_slack.js");
  console.log("News Desk — done:", (steps.notify && steps.notify.$return_value) || "");
})().catch((e) => { console.error("News Desk FAILED:", e); process.exit(1); });
