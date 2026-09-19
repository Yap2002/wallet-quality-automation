const byTestId = (id) => document.querySelector(`[data-testid="${id}"]`);
const result = byTestId("result");

function randomUuid() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();

  const bytes = new Uint8Array(16);
  if (globalThis.crypto?.getRandomValues) {
    globalThis.crypto.getRandomValues(bytes);
  } else {
    for (let index = 0; index < bytes.length; index += 1) {
      bytes[index] = Math.floor(Math.random() * 256);
    }
  }
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (value) => value.toString(16).padStart(2, "0"));
  return `${hex.slice(0, 4).join("")}-${hex.slice(4, 6).join("")}-${hex.slice(6, 8).join("")}-${hex.slice(8, 10).join("")}-${hex.slice(10).join("")}`;
}

function headers(withIdempotency = false) {
  const value = byTestId("api-key").value.trim();
  const items = { "Authorization": `Bearer ${value}`, "X-Trace-ID": randomUuid() };
  if (withIdempotency) items["Idempotency-Key"] = `ui-${randomUuid()}`;
  return items;
}

function show(kind, message) {
  result.dataset.kind = kind;
  result.textContent = message;
}

async function parse(response) {
  const body = await response.json();
  if (!response.ok) throw new Error(`${body.code || "REQUEST_FAILED"}: ${body.message || "请求失败"}`);
  return body;
}

async function refreshBalance(showStatus = true) {
  if (showStatus) show("idle", "正在查询…");
  try {
    const walletId = byTestId("wallet-id").value.trim();
    const body = await parse(await fetch(`/api/v1/wallets/${walletId}`, { headers: headers() }));
    byTestId("balance").textContent = body.balance;
    if (showStatus) show("success", "余额查询成功 · trace 可用于日志定位");
  } catch (error) {
    show("error", error.message);
  }
}

byTestId("query-balance").addEventListener("click", async () => {
  await refreshBalance();
});

byTestId("submit-transfer").addEventListener("click", async () => {
  show("idle", "正在提交…");
  try {
    const payload = {
      source_wallet_id: byTestId("wallet-id").value.trim(),
      destination_wallet_id: byTestId("destination-wallet-id").value.trim(),
      amount: byTestId("amount").value.trim(),
    };
    const body = await parse(await fetch("/api/v1/transfers", {
      method: "POST",
      headers: { ...headers(true), "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }));
    show("success", `转账成功 · 交易 ${body.id} · 手续费 ${body.fee_amount}`);
    await refreshBalance(false);
  } catch (error) {
    show("error", error.message);
  }
});
