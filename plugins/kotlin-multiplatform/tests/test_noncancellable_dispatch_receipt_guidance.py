from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "kmp-data-layer" / "SKILL.md"
READINESS = ROOT / "references" / "data-layer-readiness.md"


class PromptCancellationSchedule:
    """Executable model of the documented dispatcher-return schedule."""

    def __init__(self) -> None:
        self.events: list[str] = []
        self.cancelled = False
        self.caller_queue: list[tuple[bool, str]] = []

    def commit_and_queue_return(
        self, *, admitted: bool, outer_noncancellable: bool
    ) -> None:
        self.events.append("finalAuthorityCheck")
        if not admitted:
            self.events.append("rejected")
            return

        self.events.extend(("durableCommitted", "receiptReady", "returnQueued"))
        self.caller_queue.append((outer_noncancellable, "revision-7"))

    def cancel_caller(self) -> None:
        self.cancelled = True
        self.events.append("cancelRequested")

    def release_caller_return(self) -> None:
        outer_noncancellable, receipt = self.caller_queue.pop(0)
        self.events.append("returnReleased")

        if self.cancelled and not outer_noncancellable:
            self.events.append("cancellationEmerged")
            return

        self.events.append(f"wakeAccepted:{receipt}")
        if self.cancelled:
            self.events.append("cancellationEmerged")
            return

        self.events.extend((f"typedReturn:{receipt}", "laterCallerEffect"))


def normalized(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split()).lower()


class NonCancellableDispatchReceiptGuidanceTest(unittest.TestCase):
    def test_hot_path_names_the_receipt_loss_and_safe_boundary(self):
        text = normalized(SKILL).replace("`", "")

        for invariant in (
            "dispatcher-changing withcontext has a prompt-cancellable return hop",
            "durably commit, yet cancellation of the original context can discard its returned receipt",
            "do not place that publication after withcontext(noncancellable + iodispatcher)",
            "after the final admission/authority check, enter withcontext(noncancellable) on the caller dispatcher",
            "nest withcontext(iodispatcher) for the durable write",
            "publish before leaving the outer boundary",
            "await a bounded, identity-bound local acceptance rather than detached observation",
            "call ensureactive() before later caller-owned effects",
            "cancelled caller does not receive the typed return",
        ):
            self.assertIn(invariant, text)

    def test_readiness_reference_orders_required_publication_before_cancellation(self):
        text = normalized(READINESS).replace("`", "")

        for invariant in (
            "cancellation-atomic dispatcher hops",
            "noncancellable + iodispatcher",
            "prompt-cancellable return dispatch can replace the caller's observation of an accepted receipt",
            "outer same-dispatcher noncancellable boundary",
            "acceptedauthoritycommit",
            "publishrequired(receipt)",
            "wakeaccepted",
            "currentcoroutinecontext().ensureactive()",
            "enter the outer boundary only after final admission and authority validation",
            "protected publisher must be a bounded local handoff or durable enqueue",
            "remote or retrying delivery belongs behind the ordered idempotent notification record",
            "returnqueued without running that continuation",
            "wakeaccepted identifies the exact typed receipt before cancellation emerges",
            "cancelled caller receives no typed return",
            "later caller-owned effect does not run",
        ):
            self.assertIn(invariant, text)

        safe_start = text.index("instead, keep the dispatcher hop")
        safe_end = text.index("enter the outer boundary only", safe_start)
        safe_block = text[safe_start:safe_end]
        self.assertLess(
            safe_block.index("publishrequired(receipt)"),
            safe_block.index("currentcoroutinecontext().ensureactive()"),
        )

    def test_held_return_schedule_distinguishes_commit_from_required_publication(self):
        unsafe = PromptCancellationSchedule()
        unsafe.commit_and_queue_return(admitted=True, outer_noncancellable=False)
        unsafe.cancel_caller()
        unsafe.release_caller_return()
        unsafe_order = (
            "durableCommitted",
            "receiptReady",
            "returnQueued",
            "cancelRequested",
            "returnReleased",
            "cancellationEmerged",
        )
        for earlier, later in zip(unsafe_order, unsafe_order[1:]):
            self.assertLess(unsafe.events.index(earlier), unsafe.events.index(later))
        self.assertIn("durableCommitted", unsafe.events)
        self.assertNotIn("wakeAccepted:revision-7", unsafe.events)

        safe = PromptCancellationSchedule()
        safe.commit_and_queue_return(admitted=True, outer_noncancellable=True)
        safe.cancel_caller()
        safe.release_caller_return()
        safe_order = (
            "durableCommitted",
            "receiptReady",
            "returnQueued",
            "cancelRequested",
            "returnReleased",
            "wakeAccepted:revision-7",
            "cancellationEmerged",
        )
        for earlier, later in zip(safe_order, safe_order[1:]):
            self.assertLess(safe.events.index(earlier), safe.events.index(later))
        self.assertNotIn("typedReturn:revision-7", safe.events)
        self.assertNotIn("laterCallerEffect", safe.events)

        no_authority = PromptCancellationSchedule()
        no_authority.commit_and_queue_return(
            admitted=False, outer_noncancellable=True
        )
        self.assertEqual(["finalAuthorityCheck", "rejected"], no_authority.events)

        control = PromptCancellationSchedule()
        control.commit_and_queue_return(admitted=True, outer_noncancellable=True)
        control.release_caller_return()
        self.assertLess(
            control.events.index("wakeAccepted:revision-7"),
            control.events.index("typedReturn:revision-7"),
        )
        self.assertIn("laterCallerEffect", control.events)

    def test_guidance_is_public_safe_ascii(self):
        for path in (SKILL, READINESS):
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.isascii())
            self.assertNotIn("/Users/", text)
            self.assertNotIn("\\Users\\", text)


if __name__ == "__main__":
    unittest.main()
