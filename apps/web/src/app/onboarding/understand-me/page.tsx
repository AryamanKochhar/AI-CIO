"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button, Card, EmptyState, PageHeader, ProgressBar } from "@ai-cio/ui";
import type { InstrumentQuestion } from "@ai-cio/contracts";
import { ApiError } from "@/lib/api-client";
import { psychometricsApi, userApi } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";

function confidenceFor(question: InstrumentQuestion, elapsedMs: number): number {
  const words = Math.max(1, question.text.split(/\s+/).length);
  const target = Math.max(10, Math.min(45, 7 + words * 0.8));
  const seconds = Math.max(0, elapsedMs / 1000);
  const diff = (seconds - target) / (target * 0.65);
  const timing = 100 * Math.exp(-(diff * diff));
  const completion = Math.min(100, (seconds / target) * 100);
  return Math.round(Math.max(0, Math.min(100, timing * 0.75 + completion * 0.25)));
}

export default function UnderstandMePage() {
  const router = useRouter();
  const { user, setUser, sessionId, setSessionId } = useAuth();
  const [questions, setQuestions] = useState<InstrumentQuestion[]>([]);
  const [index, setIndex] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [startedAt, setStartedAt] = useState<number>(Date.now());
  const [observations, setObservations] = useState<string[]>([]);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function bootstrap() {
      try {
        let activeUser = user;
        if (!activeUser) {
          activeUser = await userApi.create("Guest");
          setUser(activeUser);
        }
        const [{ questions: qs }, session] = await Promise.all([
          psychometricsApi.getQuestions(),
          sessionId
            ? Promise.resolve({ id: sessionId } as { id: number })
            : psychometricsApi.startAssessment(activeUser.id),
        ]);
        if (!sessionId) setSessionId(session.id);
        setQuestions(qs);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Unable to load questionnaire.");
      } finally {
        setLoading(false);
      }
    }
    bootstrap();
  }, [user, sessionId, setUser, setSessionId]);

  async function submitAnswer() {
    if (!sessionId || !selected || !questions[index]) return;
    setError(null);
    const question = questions[index];
    const elapsed = Date.now() - startedAt;
    try {
      await psychometricsApi.submitResponse(sessionId, {
        question_id: question.id,
        answer: selected,
        confidence: confidenceFor(question, elapsed),
        response_time_ms: elapsed,
      });
      const next = index + 1;
      if (next >= questions.length) {
        await psychometricsApi.complete(sessionId);
        const obs = await psychometricsApi.getObservations(sessionId);
        setObservations(obs.observations);
        setDone(true);
      } else {
        setIndex(next);
        setSelected(null);
        setStartedAt(Date.now());
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "We couldn't save that answer. Please try again.");
    }
  }

  if (loading) {
    return <EmptyState title="Loading your questionnaire" description="Preparing a calm, one-question-at-a-time experience." />;
  }

  if (done) {
    return (
      <Card>
        <PageHeader
          title="How you tend to decide"
          description="This is a behavioural sketch from your answers — not a diagnosis and not an investment recommendation."
        />
        <ul className="mb-6 space-y-2 text-sm text-slate-700">
          {observations.map((item) => (
            <li key={item}>• {item}</li>
          ))}
        </ul>
        <Link href="/onboarding/finances">
          <Button>Continue to my finances</Button>
        </Link>
      </Card>
    );
  }

  const question = questions[index];
  if (!question) {
    return <EmptyState title="No questions available" description="Start the API and ensure the instrument is seeded." />;
  }

  return (
    <Card>
      <PageHeader title="A few questions about how you decide" description="Take your time. There are no right or wrong answers." />
      <ProgressBar value={((index + 1) / questions.length) * 100} label={`Question ${index + 1} of ${questions.length}`} />
      <p className="my-6 text-base leading-relaxed text-slate-800">{question.text}</p>
      <div className="space-y-2">
        {question.options.map((option) => (
          <button
            key={option.id}
            type="button"
            onClick={() => setSelected(option.id)}
            className={`w-full rounded-xl border px-4 py-3 text-left text-sm transition ${
              selected === option.id
                ? "border-slate-900 bg-slate-900 text-white"
                : "border-slate-200 bg-white text-slate-800 hover:border-slate-300"
            }`}
          >
            {option.text}
          </button>
        ))}
      </div>
      {error ? <p className="mt-4 text-sm text-red-600">{error}</p> : null}
      <div className="mt-6 flex justify-end">
        <Button onClick={submitAnswer} disabled={!selected}>
          {index + 1 === questions.length ? "Finish" : "Continue"}
        </Button>
      </div>
    </Card>
  );
}
