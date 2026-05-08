import json
import logging
import sys
import time
from pathlib import Path

from app.services.jira_client import _parse_ticket
from app.services.llm_client import summarize_ticket

DATA_FILE = Path(__file__).resolve().parents[1] / "app" / "data" / "jira_tickets.json"


class AttemptCounter(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.INFO)
        self.attempts = 0

    def emit(self, record):
        if "attempt " in record.getMessage() and "Sending ticket" in record.getMessage():
            self.attempts += 1


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 2

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    with DATA_FILE.open("r", encoding="utf-8") as f:
        raw_tickets = json.load(f)

    tickets = [_parse_ticket(t) for t in raw_tickets[:count]]
    print(f"\n=== Running summarize_ticket on {len(tickets)} ticket(s) ===\n")

    report = []
    for ticket in tickets:
        counter = AttemptCounter()
        logging.getLogger("app.services.llm_client").addHandler(counter)
        started = time.monotonic()
        try:
            result = summarize_ticket(ticket)
            elapsed = time.monotonic() - started
            report.append({
                "key": ticket.key,
                "attempts": counter.attempts,
                "elapsed_s": round(elapsed, 2),
                "summary": result.summary,
                "label": result.label,
                "error": None,
            })
        except Exception as e:
            elapsed = time.monotonic() - started
            report.append({
                "key": ticket.key,
                "attempts": counter.attempts,
                "elapsed_s": round(elapsed, 2),
                "summary": None,
                "error": f"{type(e).__name__}: {e}",
            })
        finally:
            logging.getLogger("app.services.llm_client").removeHandler(counter)

    print("\n=== Summary ===")
    for row in report:
        status = "OK " if row["error"] is None else "FAIL"
        print(f"[{status}] {row['key']:20s} attempts={row['attempts']:2d}  time={row['elapsed_s']}s")
        if row["summary"]:
            print(f"        → [{row.get('label')}] {row['summary']}")
        if row["error"]:
            print(f"        ! {row['error']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
