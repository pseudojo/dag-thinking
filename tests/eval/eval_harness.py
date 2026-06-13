"""LLM 연동 평가 하네스 — 세션 흐름 자동 기록 및 토큰 메트릭 측정.

사용법은 docs/EVAL_PLAN.md §4 참조.
LLM 클라이언트는 Protocol로 주입 — 특정 SDK 의존 없음.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


class EvalHarness:
    """세션 흐름을 기록하고 토큰 메트릭을 측정하는 평가 하네스."""

    def __init__(self, session_id: str, output_dir: str = "tests/eval/results") -> None:
        self.session_id = session_id
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.flow_log: list[dict] = []
        self.token_metrics: dict[str, int] = {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_tokens": 0,
        }

    def record_turn(
        self,
        turn_index: int,
        messages: list[dict],
        tool_calls: list[dict],
        tool_results: list[dict],
        usage: dict[str, int],
    ) -> None:
        """LLM 한 턴의 입출력과 토큰 사용량을 기록."""
        self.flow_log.append(
            {
                "turn_index": turn_index,
                "timestamp": datetime.now().isoformat(),
                "messages": messages,
                "tool_calls": tool_calls,
                "tool_results": tool_results,
                "usage": usage,
            }
        )
        input_t = usage.get("input_tokens", 0)
        output_t = usage.get("output_tokens", 0)
        self.token_metrics["total_input_tokens"] += input_t
        self.token_metrics["total_output_tokens"] += output_t
        self.token_metrics["total_tokens"] += input_t + output_t

    def save(self) -> Path:
        """기록된 흐름과 메트릭을 JSON 파일로 저장."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = self.output_dir / f"eval_{self.session_id}_{timestamp}.json"
        with fname.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "session_id": self.session_id,
                    "token_metrics": self.token_metrics,
                    "turn_count": len(self.flow_log),
                    "flow_log": self.flow_log,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
        return fname

    def summary(self) -> dict:
        """평가 세션 요약 메트릭 반환."""
        return {
            "session_id": self.session_id,
            "total_turns": len(self.flow_log),
            **self.token_metrics,
        }
