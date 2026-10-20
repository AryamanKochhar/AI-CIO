"""Investment decision orchestration."""

def run_decision(*args, **kwargs):
    # Keep model transport instrumentation importable without constructing the
    # coordinator (which itself imports the model client).
    from ai_cio.services.orchestration.coordinator import run_decision as execute
    return execute(*args, **kwargs)

__all__ = ["run_decision"]
