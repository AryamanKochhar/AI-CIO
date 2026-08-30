"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
  ProgressBar,
} from "@ai-cio/ui";
import type { InstrumentQuestion } from "@ai-cio/contracts";
import { ApiError } from "@/lib/api-client";
import { psychometricsApi } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";
import { useJourney } from "@/hooks/use-journey";

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
  const user = useAuth().user;
  const { setStep } = useJourney();
  const { sessionId, setSessionId } = useAuth();
  const [questions, setQuestions] = useState<InstrumentQuestion[]>([]);
  const [index, setIndex] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [startedAt, setStartedAt] = useState(Date.now());
  const [observations, setObservations] = useState<string[]>([]);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!user) return;
    async function bootstrap() {
      try {
        const { questions: qs } = await psychometricsApi.getQuestions();
        setQuestions(qs);
        const active = await psychometricsApi.getActive(user!.id);
        if (active.active && active.session_id) {
          setSessionId(active.session_id);
          setIndex(active.answered_count ?? 0);
        } else if (!sessionId) {
          const session = await psychometricsApi.startAssessment(user!.id);
          setSessionId(session.id);
        }
        await setStep("psychometrics");
      } catch (err) {
        if (err instanceof ApiError && err.message.includes("Profile not found") === false) {
          setError(err.message);
        }
        try {
          const obs = sessionId ? await psychometricsApi.getObservations(sessionId) : null;
          if (obs?.observations?.length) {
            setObservations(obs.observations);
            setDone(true);
          }
        } catch {
          /* no completed profile yet */
        }
      } finally {
        setLoading(false);
      }
    }
    bootstrap();
  }, [user, sessionId, setSessionId, setStep]);

  async function submitAnswer() {
    if (!sessionId || !selected || !questions[index]) return;
    setSubmitting(true);
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
        await setStep("finances");
      } else {
        setIndex(next);
        setSelected(null);
        setStartedAt(Date.now());
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "We couldn't save that answer. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  function goBack() {
    if (index > 0) {
      setIndex(index - 1);
      setSelected(null);
      setStartedAt(Date.now());
    }
  }

  if (!user) {
    return (
      <Card>
        <PageHeader title="Understand me" description="Please sign in to continue." />
        <Link href="/login"><Button>Sign in</Button></Link>
      </Card>
    );
  }

  if (loading) return <LoadingState message="Preparing your assessment…" />;
  if (error && !done) return <ErrorState title="Unable to load assessment" message={error} />;

  if (done) {
    return (
      <Card className="aic-card-glow">
        <PageHeader
          title="Here's what we learned about you"
          description="A concise behavioural sketch from your answers — not a diagnosis and not an investment recommendation."
        />
        <ul className="mb-6 space-y-3 text-sm leading-relaxed text-slate-700">
          {observations.map((item) => (
            <li key={item} className="rounded-lg bg-slate-50 px-4 py-3">{item}</li>
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
    return <EmptyState title="No questions available" description="Ensure the API is running and the instrument is seeded." />;
  }

  return (
    <Card className="aic-card-glow">
      <PageHeader
        title="Let's understand how you make financial decisions"
        description="There are no right or wrong answers. Take your time."
      />
      <ProgressBar value={((index + 1) / questions.length) * 100} label={`${index + 1} of ${questions.length}`} />
      <p className="my-6 text-base leading-relaxed text-slate-800">{question.text}</p>
      <div className="space-y-2" role="radiogroup" aria-label="Answer choices">
        {question.options.map((option) => (
          <button
            key={option.id}
            type="button"
            role="radio"
            aria-checked={selected === option.id}
            onClick={() => setSelected(option.id)}
            className={`w-full rounded-xl border px-4 py-3.5 text-left text-sm transition ${
              selected === option.id
                ? "border-slate-900 bg-slate-900 text-white"
                : "border-slate-200 bg-white text-slate-800 hover:border-slate-300"
            }`}
          >
            {option.text}
          </button>
        ))}
      </div>
      {error ? <p className="mt-4 text-sm text-red-600" role="alert">{error}</p> : null}
      <div className="mt-6 flex justify-between gap-3">
        <Button variant="secondary" onClick={goBack} disabled={index === 0 || submitting}>
          Back
        </Button>
        <Button onClick={submitAnswer} disabled={!selected || submitting}>
          {submitting ? "Saving…" : index + 1 === questions.length ? "Finish" : "Continue"}
        </Button>
      </div>
    </Card>
  );
}
