import assert from "node:assert/strict";
import test from "node:test";
import type { DigitalTwin } from "@ai-cio/contracts";
import {
  activateWorkspaceUser, clearTwinSnapshot, financialMutationUser,
  MAX_SNAPSHOT_CHARS, readTwinSnapshot, TWIN_SNAPSHOT_TTL_MS, writeTwinSnapshot,
} from "../workspace-cache.ts";

function storage() {
  const rows = new Map<string, string>();
  return {
    rows,
    getItem: (key: string) => rows.get(key) ?? null,
    setItem: (key: string, value: string) => { rows.set(key, value); },
    removeItem: (key: string) => { rows.delete(key); },
  };
}
function twin(userId: number): DigitalTwin {
  return { user: { id: userId, name: "Synthetic" }, completeness: { income: true }, goals: { items: [] } } as unknown as DigitalTwin;
}

test("snapshot survives a same-user reload within TTL and expires closed", () => {
  const store = storage(); activateWorkspaceUser(7, store);
  assert.equal(writeTwinSnapshot(7, twin(7), store, 1000), true);
  assert.equal(readTwinSnapshot(7, store, 2000)?.twin.user.id, 7);
  assert.equal(readTwinSnapshot(7, store, 1000 + TWIN_SNAPSHOT_TTL_MS), undefined);
  assert.equal(store.rows.size, 0);
});

test("account switch, logout and late old-user requests cannot leak a snapshot", () => {
  const store = storage(); activateWorkspaceUser(7, store);
  writeTwinSnapshot(7, twin(7), store, 1000);
  activateWorkspaceUser(8, store);
  assert.equal(store.rows.size, 0);
  assert.equal(writeTwinSnapshot(7, twin(7), store, 1100), false);
  assert.equal(writeTwinSnapshot(8, twin(8), store, 1100), true);
  assert.equal(readTwinSnapshot(7, store, 1200), undefined);
  activateWorkspaceUser(null, store);
  assert.equal(writeTwinSnapshot(8, twin(8), store, 1200), false);
  assert.equal(store.rows.size, 0);
});

test("cache remains one bounded entry and rejects oversized financial snapshots", () => {
  const store = storage(); activateWorkspaceUser(3, store);
  for (let i = 0; i < 20; i++) writeTwinSnapshot(3, twin(3), store, 1000 + i);
  assert.equal(store.rows.size, 1);
  const large = twin(3); large.user.name = "x".repeat(MAX_SNAPSHOT_CHARS);
  assert.equal(writeTwinSnapshot(3, large, store, 2000), false);
  assert.equal(store.rows.size, 0);
});

test("corrupt, future-dated and mismatched-server snapshots fail closed", () => {
  const store = storage(); activateWorkspaceUser(3, store);
  writeTwinSnapshot(3, twin(3), store, 1000);
  assert.equal(readTwinSnapshot(3, store, 500), undefined);
  writeTwinSnapshot(3, twin(3), store, 1000);
  const [key, raw] = [...store.rows][0];
  const row = JSON.parse(raw); row.api = "https://different-server.example";
  store.setItem(key, JSON.stringify(row));
  assert.equal(readTwinSnapshot(3, store, 1500), undefined);
  store.setItem(key, "{broken");
  assert.equal(readTwinSnapshot(3, store, 1500), undefined);
  clearTwinSnapshot(undefined, store);
});

test("only persisted financial mutations invalidate the workspace", () => {
  assert.equal(financialMutationUser("/users/7/finances", "PUT"), 7);
  assert.equal(financialMutationUser("/users/7/goals/42", "DELETE"), 7);
  assert.equal(financialMutationUser("/users/7/fixed-deposits", "POST"), 7);
  assert.equal(financialMutationUser("/assessments/4/complete", "POST"), null);
  assert.equal(financialMutationUser("/users/7/finances", "GET"), undefined);
  assert.equal(financialMutationUser("/users/7/decisions/what-if", "POST"), undefined);
  assert.equal(financialMutationUser("/auth/login", "POST"), undefined);
});
