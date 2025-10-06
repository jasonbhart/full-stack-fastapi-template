"""Evaluator for agent outputs."""

import asyncio
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import openai
from langfuse import Langfuse
from langfuse.api.resources.commons.types.trace_with_details import TraceWithDetails
from tqdm import tqdm

from app.core.config import settings
from app.core.logging import logger
from app.evaluation.metrics import metrics
from app.evaluation.schemas import ScoreSchema


class Evaluator:
    """Evaluates model outputs using predefined metrics.

    Fetches traces from Langfuse, evaluates them against metrics,
    and uploads scores back to Langfuse.
    """

    def __init__(self) -> None:
        """Initialize Evaluator with OpenAI and Langfuse clients."""
        self.client = openai.AsyncOpenAI(
            api_key=settings.EVALUATION_API_KEY, base_url=settings.EVALUATION_BASE_URL
        )
        self.langfuse = Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_HOST,
        )
        self.report: dict[str, Any] = self._initialize_report()

    async def run(self, generate_report_file: bool = True) -> dict[str, Any]:
        """Run evaluation on recent traces.

        Args:
            generate_report_file: Whether to save a JSON report file

        Returns:
            Evaluation report dictionary
        """
        start_time = time.time()
        traces = self._fetch_traces()
        self.report["total_traces"] = len(traces)

        trace_results: dict[str, dict[str, Any]] = {}

        for trace in tqdm(traces, desc="Evaluating traces"):
            trace_id = trace.id
            trace_results[trace_id] = {
                "success": False,
                "metrics_evaluated": 0,
                "metrics_succeeded": 0,
                "metrics_results": {},
            }

            for metric in tqdm(metrics, desc=f"Trace {trace_id[:8]}", leave=False):
                metric_name = metric["name"]
                input_text, output_text = self._get_input_output(trace)
                score = await self._evaluate_metric(metric, input_text, output_text)

                if score:
                    self._push_score_to_langfuse(trace, score, metric)
                    self._update_success_metrics(trace_id, metric_name, score, trace_results)
                else:
                    self._update_failure_metrics(trace_id, metric_name, trace_results)

                trace_results[trace_id]["metrics_evaluated"] += 1

            self._process_trace_results(trace_id, trace_results, len(metrics))
            await asyncio.sleep(settings.EVALUATION_SLEEP_TIME)

        self.report["duration_seconds"] = round(time.time() - start_time, 2)
        self._calculate_avg_scores()

        if generate_report_file:
            self._save_report()

        logger.info(
            f"Evaluation completed: {self.report['successful_traces']}/{self.report['total_traces']} traces succeeded "
            f"({self.report['failed_traces']} failed) in {self.report['duration_seconds']}s"
        )

        return self.report

    def _initialize_report(self) -> dict[str, Any]:
        """Initialize report structure."""
        report: dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "model": settings.EVALUATION_LLM,
            "total_traces": 0,
            "successful_traces": 0,
            "failed_traces": 0,
            "duration_seconds": 0,
            "metrics_summary": {},
            "successful_traces_details": [],
            "failed_traces_details": [],
        }

        # Initialize metrics summary
        for metric in metrics:
            report["metrics_summary"][metric["name"]] = {
                "success_count": 0,
                "failure_count": 0,
                "avg_score": 0.0,
            }

        return report

    def _fetch_traces(self) -> list[TraceWithDetails]:
        """Fetch traces from the past 24 hours without scores."""
        last_24_hours = datetime.now() - timedelta(hours=24)
        try:
            traces = self.langfuse.api.trace.list(
                from_timestamp=last_24_hours, order_by="timestamp.asc", limit=100
            ).data
            return [trace for trace in traces if not trace.scores]
        except Exception as e:
            logger.error(f"Error fetching traces: {e}")
            return []

    def _get_input_output(self, trace: TraceWithDetails) -> tuple[str | None, str | None]:
        """Extract input and output from trace."""
        if not isinstance(trace.output, dict):
            return None, None

        messages = trace.output.get("messages", [])
        if not messages:
            return None, None

        input_messages = messages[:-1]
        output_message = messages[-1]

        return self._format_messages(input_messages), self._format_messages([output_message])

    def _format_messages(self, messages: list[dict[str, Any]]) -> str:
        """Format messages for evaluation."""
        formatted = []
        for msg in messages:
            if msg.get("type") == "tool":
                content = msg.get("content", "")
                if isinstance(content, str) and len(content) > 100:
                    formatted.append(f"tool {msg.get('name')}: {content[:100]}...")
                else:
                    formatted.append(f"tool {msg.get('name')}: {content}")
            elif msg.get("content"):
                formatted.append(f"{msg['type']}: {msg['content']}")
        return "\n".join(formatted)

    async def _evaluate_metric(
        self, metric: dict[str, str], input_text: str | None, output_text: str | None
    ) -> ScoreSchema | None:
        """Evaluate a trace against a metric."""
        if not input_text or not output_text:
            logger.warning(f"Skipping {metric['name']}: missing input or output")
            return None

        for attempt in range(3):  # Retry up to 3 times
            try:
                response = await self.client.beta.chat.completions.parse(
                    model=settings.EVALUATION_LLM,
                    messages=[
                        {"role": "system", "content": metric["prompt"]},
                        {"role": "user", "content": f"Input: {input_text}\nGeneration: {output_text}"},
                    ],
                    response_format=ScoreSchema,
                )
                return response.choices[0].message.parsed
            except Exception as e:
                if attempt < 2:
                    logger.warning(f"Evaluation attempt {attempt + 1} failed, retrying: {e}")
                    await asyncio.sleep(10)
                else:
                    logger.error(f"Evaluation failed after 3 attempts: {e}")
                    return None
        return None

    def _push_score_to_langfuse(
        self, trace: TraceWithDetails, score: ScoreSchema, metric: dict[str, str]
    ) -> None:
        """Push evaluation score to Langfuse."""
        self.langfuse.create_score(
            trace_id=trace.id,
            name=metric["name"],
            data_type="NUMERIC",
            value=score.score,
            comment=score.reasoning,
        )

    def _update_success_metrics(
        self,
        trace_id: str,
        metric_name: str,
        score: ScoreSchema,
        trace_results: dict[str, dict[str, Any]],
    ) -> None:
        """Update metrics for successful evaluation."""
        trace_results[trace_id]["metrics_succeeded"] += 1
        trace_results[trace_id]["metrics_results"][metric_name] = {
            "success": True,
            "score": score.score,
            "reasoning": score.reasoning,
        }
        self.report["metrics_summary"][metric_name]["success_count"] += 1
        self.report["metrics_summary"][metric_name]["avg_score"] += score.score

    def _update_failure_metrics(
        self, trace_id: str, metric_name: str, trace_results: dict[str, dict[str, Any]]
    ) -> None:
        """Update metrics for failed evaluation."""
        trace_results[trace_id]["metrics_results"][metric_name] = {"success": False}
        self.report["metrics_summary"][metric_name]["failure_count"] += 1

    def _process_trace_results(
        self, trace_id: str, trace_results: dict[str, dict[str, Any]], total_metrics: int
    ) -> None:
        """Process results for a single trace."""
        if trace_results[trace_id]["metrics_succeeded"] == total_metrics:
            trace_results[trace_id]["success"] = True
            self.report["successful_traces"] += 1
            self.report["successful_traces_details"].append(
                {"trace_id": trace_id, "metrics_results": trace_results[trace_id]["metrics_results"]}
            )
        else:
            self.report["failed_traces"] += 1
            self.report["failed_traces_details"].append(
                {
                    "trace_id": trace_id,
                    "metrics_evaluated": trace_results[trace_id]["metrics_evaluated"],
                    "metrics_succeeded": trace_results[trace_id]["metrics_succeeded"],
                    "metrics_results": trace_results[trace_id]["metrics_results"],
                }
            )

    def _calculate_avg_scores(self) -> None:
        """Calculate average scores for each metric."""
        for data in self.report["metrics_summary"].values():
            if data["success_count"] > 0:
                data["avg_score"] = round(data["avg_score"] / data["success_count"], 2)

    def _save_report(self) -> str:
        """Save evaluation report to JSON file."""
        report_dir = Path.cwd() / "reports"
        report_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = report_dir / f"evaluation_report_{timestamp}.json"

        report_path.write_text(json.dumps(self.report, indent=2))

        self.report["report_path"] = str(report_path)
        logger.info(f"Report saved: {report_path}")
        return str(report_path)
