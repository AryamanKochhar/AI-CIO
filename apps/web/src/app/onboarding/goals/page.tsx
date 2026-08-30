"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button, Card, EmptyState, GoalCard, Input, Label, PageHeader } from "@ai-cio/ui";
import type { Goal } from "@ai-cio/contracts";
import { formatCurrency } from "@ai-cio/utils";
import { ApiError } from "@/lib/api-client";
import { goalsApi } from "@/lib/api";
import { GOAL_TYPES } from "@/lib/constants";
import { useRequireAuth, useJourney } from "@/hooks/use-journey";

export default function GoalsPage() {
  const user = useRequireAuth();
  const router = useRouter();
  const { setStep } = useJourney();
  const [goals, setGoals] = useState<Goal[]>([]);
  const [goalType, setGoalType] = useState("emergency");
  const [name, setName] = useState("");
  const [targetAmount, setTargetAmount] = useState("");
  const [targetDate, setTargetDate] = useState("");
  const [currentFunding, setCurrentFunding] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    if (!user) return;
    setGoals(await goalsApi.list(user.id));
    setLoading(false);
  }

  useEffect(() => {
    refresh().catch(() => setLoading(false));
  }, [user]);

  async function addGoal(event: React.FormEvent) {
    event.preventDefault();
    if (!user) return;
    setError(null);
    try {
      await goalsApi.create(user.id, {
        name: name || GOAL_TYPES.find((g) => g.value === goalType)?.label,
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

  async function continueFlow() {
    await setStep("portfolio");
    router.push("/onboarding/documents");
  }

  if (!user) return null;

  return (
    <div className="space-y-6">
      <Card className="aic-card-glow">
        <PageHeader
          title="What are you working toward?"
          description="Choose a goal type, then add details. You can add several goals or skip for now."
        />
        <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {GOAL_TYPES.map((type) => (
            <GoalCard
              key={type.value}
              name={type.label}
              type="Goal"
              selected={goalType === type.value}
              onClick={() => {
                setGoalType(type.value);
                if (!name) setName(type.label);
              }}
            />
          ))}
        </div>
        <form className="grid gap-4 md:grid-cols-2" onSubmit={addGoal}>
          <div><Label htmlFor="goal-name">Goal name</Label><Input id="goal-name" value={name} onChange={(e) => setName(e.target.value)} required /></div>
          <div><Label htmlFor="target-amount">Target amount (₹)</Label><Input id="target-amount" value={targetAmount} onChange={(e) => setTargetAmount(e.target.value)} placeholder="Optional" /></div>
          <div><Label htmlFor="target-date">Target date</Label><Input id="target-date" type="date" value={targetDate} onChange={(e) => setTargetDate(e.target.value)} /></div>
          <div><Label htmlFor="current">Already saved toward this (₹)</Label><Input id="current" value={currentFunding} onChange={(e) => setCurrentFunding(e.target.value)} placeholder="Optional" /></div>
          <div className="md:col-span-2"><Button type="submit">Add goal</Button></div>
        </form>
        {error ? <p className="mt-4 text-sm text-red-600" role="alert">{error}</p> : null}
      </Card>

      <Card className="aic-card-glow">
        <h2 className="mb-4 text-base font-semibold text-slate-900">Your goals</h2>
        {loading ? (
          <p className="text-sm text-slate-600">Loading…</p>
        ) : goals.length === 0 ? (
          <EmptyState title="No goals yet" description="Add a goal above, or skip if you're not sure yet." />
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
          <Button variant="secondary" onClick={() => goalsApi.skip(user.id).then(continueFlow)}>
            Skip for now
          </Button>
          <Button onClick={continueFlow}>Continue to my portfolio</Button>
        </div>
      </Card>
    </div>
  );
}
