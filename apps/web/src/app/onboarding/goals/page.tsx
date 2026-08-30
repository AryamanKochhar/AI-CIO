"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button, Card, Input, Label, PageHeader } from "@ai-cio/ui";
import type { Goal } from "@ai-cio/contracts";
import { ApiError } from "@/lib/api-client";
import { goalsApi } from "@/lib/api";
import { GOAL_TYPES } from "@/lib/constants";
import { useAuth } from "@/hooks/use-auth";
import { formatCurrency } from "@ai-cio/utils";

export default function GoalsPage() {
  const { user } = useAuth();
  const [goals, setGoals] = useState<Goal[]>([]);
  const [name, setName] = useState("");
  const [goalType, setGoalType] = useState("emergency");
  const [targetAmount, setTargetAmount] = useState("");
  const [targetDate, setTargetDate] = useState("");
  const [currentFunding, setCurrentFunding] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    if (!user) return;
    setGoals(await goalsApi.list(user.id));
  }

  useEffect(() => {
    refresh().catch(() => undefined);
  }, [user]);

  async function addGoal(event: React.FormEvent) {
    event.preventDefault();
    if (!user) return;
    setError(null);
    try {
      await goalsApi.create(user.id, {
        name,
        goal_type: goalType,
        target_amount: targetAmount || null,
        target_date: targetDate || null,
        current_funding: currentFunding || null,
        priority: "medium",
        flexibility: "somewhat",
      });
      setName("");
      setTargetAmount("");
      setTargetDate("");
      setCurrentFunding("");
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to save goal.");
    }
  }

  if (!user) {
    return (
      <Card>
        <PageHeader title="My goals" description="Please sign in first." />
        <Link href="/login"><Button>Sign in</Button></Link>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <PageHeader
          title="What's important to you?"
          description="Add one or more goals. Amounts you leave blank stay unknown."
        />
        <div className="mb-6 flex flex-wrap gap-2">
          {GOAL_TYPES.map((type) => (
            <button
              key={type.value}
              type="button"
              onClick={() => {
                setGoalType(type.value);
                if (!name) setName(type.label);
              }}
              className={`rounded-full border px-3 py-1.5 text-sm ${
                goalType === type.value ? "border-slate-900 bg-slate-900 text-white" : "border-slate-200 bg-white"
              }`}
            >
              {type.label}
            </button>
          ))}
        </div>
        <form className="grid gap-4 md:grid-cols-2" onSubmit={addGoal}>
          <div><Label htmlFor="goal-name">Goal name</Label><Input id="goal-name" value={name} onChange={(e) => setName(e.target.value)} required /></div>
          <div><Label htmlFor="target-amount">Target amount (₹)</Label><Input id="target-amount" value={targetAmount} onChange={(e) => setTargetAmount(e.target.value)} placeholder="Optional" /></div>
          <div><Label htmlFor="target-date">Target date</Label><Input id="target-date" type="date" value={targetDate} onChange={(e) => setTargetDate(e.target.value)} /></div>
          <div><Label htmlFor="current-funding">Already saved (₹)</Label><Input id="current-funding" value={currentFunding} onChange={(e) => setCurrentFunding(e.target.value)} placeholder="Optional" /></div>
          <div className="md:col-span-2"><Button type="submit">Add goal</Button></div>
        </form>
        {error ? <p className="mt-4 text-sm text-red-600">{error}</p> : null}
      </Card>

      <Card>
        <h2 className="mb-4 text-base font-semibold text-slate-900">Your goals</h2>
        {goals.length === 0 ? (
          <p className="text-sm text-slate-600">No goals yet. You can skip this step if you're unsure.</p>
        ) : (
          <ul className="space-y-3">
            {goals.map((goal) => (
              <li key={goal.id} className="flex items-center justify-between rounded-xl border border-slate-200 px-4 py-3">
                <div>
                  <p className="font-medium text-slate-900">{goal.name}</p>
                  <p className="text-sm text-slate-600">
                    {goal.goal_type} · target {formatCurrency(goal.target_amount)}
                  </p>
                </div>
                <Button variant="ghost" onClick={() => goalsApi.remove(user.id, goal.id).then(refresh)}>
                  Remove
                </Button>
              </li>
            ))}
          </ul>
        )}
        <div className="mt-6 flex flex-wrap gap-3">
          <Button variant="secondary" onClick={() => goalsApi.skip(user.id)}>Skip for now</Button>
          <Link href="/onboarding/documents"><Button>Continue to documents</Button></Link>
        </div>
      </Card>
    </div>
  );
}
