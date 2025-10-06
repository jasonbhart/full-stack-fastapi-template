#!/usr/bin/env python3
"""
Performance Testing Script for Agent Endpoints

This script tests:
- Agent endpoint response times
- Rate limiting behavior under load
- Resource usage and throughput
- System performance characteristics

Usage:
    python scripts/performance_test.py [--base-url URL] [--concurrency N] [--duration SECONDS]
"""

import argparse
import asyncio
import json
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime
from typing import Any

import httpx
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)


class PerformanceTest:
    """Performance testing orchestrator for agent endpoints."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        concurrency: int = 10,
        duration: int = 30,
        email: str = "admin@example.com",
        password: str = "changethisnowplease",
    ):
        self.base_url = base_url.rstrip("/")
        self.concurrency = concurrency
        self.duration = duration
        self.email = email
        self.password = password
        self.token: str | None = None
        self.results: dict[str, list[float]] = defaultdict(list)
        self.errors: dict[str, int] = defaultdict(int)
        self.rate_limit_hits: int = 0
        self.total_requests: int = 0

    async def authenticate(self, client: httpx.AsyncClient) -> bool:
        """Authenticate and get access token."""
        try:
            response = await client.post(
                f"{self.base_url}/api/v1/login/access-token",
                data={"username": self.email, "password": self.password},
            )
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("access_token")
                return True
            else:
                print(
                    f"{Fore.RED}✗ Authentication failed: {response.status_code}{Style.RESET_ALL}"
                )
                return False
        except Exception as e:
            print(f"{Fore.RED}✗ Authentication error: {e}{Style.RESET_ALL}")
            return False

    def get_headers(self) -> dict[str, str]:
        """Get authorization headers."""
        if not self.token:
            return {}
        return {"Authorization": f"Bearer {self.token}"}

    async def test_agent_run(self, client: httpx.AsyncClient, test_id: int) -> dict[str, Any]:
        """Test single agent run endpoint call."""
        start_time = time.perf_counter()
        try:
            response = await client.post(
                f"{self.base_url}/api/v1/agent/run",
                json={
                    "message": f"Test message {test_id}: What is 2+2?",
                    "thread_id": f"perf-test-{test_id}",
                    "metadata": {"test": "performance"},
                },
                headers=self.get_headers(),
                timeout=30.0,
            )
            elapsed = time.perf_counter() - start_time
            self.total_requests += 1

            if response.status_code == 200:
                self.results["agent_run"].append(elapsed)
                return {"status": "success", "elapsed": elapsed, "status_code": 200}
            elif response.status_code == 429:
                self.rate_limit_hits += 1
                return {"status": "rate_limited", "elapsed": elapsed, "status_code": 429}
            else:
                self.errors[f"status_{response.status_code}"] += 1
                return {"status": "error", "elapsed": elapsed, "status_code": response.status_code}

        except httpx.TimeoutException:
            elapsed = time.perf_counter() - start_time
            self.errors["timeout"] += 1
            return {"status": "timeout", "elapsed": elapsed}
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            self.errors[f"error_{type(e).__name__}"] += 1
            return {"status": "error", "elapsed": elapsed, "error": str(e)}

    async def test_get_runs(self, client: httpx.AsyncClient) -> dict[str, Any]:
        """Test get runs endpoint."""
        start_time = time.perf_counter()
        try:
            response = await client.get(
                f"{self.base_url}/api/v1/agent/runs",
                headers=self.get_headers(),
                params={"skip": 0, "limit": 10},
                timeout=10.0,
            )
            elapsed = time.perf_counter() - start_time
            self.total_requests += 1

            if response.status_code == 200:
                self.results["get_runs"].append(elapsed)
                return {"status": "success", "elapsed": elapsed}
            elif response.status_code == 429:
                self.rate_limit_hits += 1
                return {"status": "rate_limited", "elapsed": elapsed}
            else:
                self.errors[f"get_runs_status_{response.status_code}"] += 1
                return {"status": "error", "elapsed": elapsed}

        except Exception as e:
            elapsed = time.perf_counter() - start_time
            self.errors[f"get_runs_error_{type(e).__name__}"] += 1
            return {"status": "error", "elapsed": elapsed, "error": str(e)}

    async def test_health_check(self, client: httpx.AsyncClient) -> dict[str, Any]:
        """Test health check endpoint (no auth required)."""
        start_time = time.perf_counter()
        try:
            response = await client.get(
                f"{self.base_url}/api/v1/agent/health",
                timeout=5.0,
            )
            elapsed = time.perf_counter() - start_time
            self.total_requests += 1

            if response.status_code == 200:
                self.results["health_check"].append(elapsed)
                return {"status": "success", "elapsed": elapsed}
            else:
                self.errors[f"health_status_{response.status_code}"] += 1
                return {"status": "error", "elapsed": elapsed}

        except Exception as e:
            elapsed = time.perf_counter() - start_time
            self.errors[f"health_error_{type(e).__name__}"] += 1
            return {"status": "error", "elapsed": elapsed}

    async def worker(self, worker_id: int, stop_event: asyncio.Event):
        """Worker that continuously sends requests until duration expires."""
        async with httpx.AsyncClient() as client:
            # Authenticate once per worker
            if not await self.authenticate(client):
                print(f"{Fore.RED}Worker {worker_id} failed to authenticate{Style.RESET_ALL}")
                return

            request_count = 0
            while not stop_event.is_set():
                # Mix of different endpoint tests
                if request_count % 5 == 0:
                    await self.test_health_check(client)
                elif request_count % 3 == 0:
                    await self.test_get_runs(client)
                else:
                    await self.test_agent_run(client, worker_id * 10000 + request_count)

                request_count += 1
                # Small delay to avoid overwhelming the system
                await asyncio.sleep(0.1)

    async def run_load_test(self):
        """Run concurrent load test for specified duration."""
        print(f"\n{Fore.CYAN}{'='*80}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Performance Test Configuration{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}")
        print(f"Base URL:       {self.base_url}")
        print(f"Concurrency:    {self.concurrency} workers")
        print(f"Duration:       {self.duration} seconds")
        print(f"Authentication: {self.email}")
        print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}\n")

        # Test authentication first
        async with httpx.AsyncClient() as client:
            if not await self.authenticate(client):
                print(f"{Fore.RED}✗ Failed to authenticate. Check credentials.{Style.RESET_ALL}")
                sys.exit(1)
            print(f"{Fore.GREEN}✓ Authentication successful{Style.RESET_ALL}\n")

        # Create stop event
        stop_event = asyncio.Event()

        # Start workers
        print(f"{Fore.YELLOW}Starting {self.concurrency} workers...{Style.RESET_ALL}")
        start_time = time.time()
        workers = [asyncio.create_task(self.worker(i, stop_event)) for i in range(self.concurrency)]

        # Wait for duration
        await asyncio.sleep(self.duration)

        # Stop workers
        stop_event.set()
        print(f"{Fore.YELLOW}Stopping workers...{Style.RESET_ALL}")
        await asyncio.gather(*workers, return_exceptions=True)

        elapsed_time = time.time() - start_time
        self.print_results(elapsed_time)

    def print_results(self, elapsed_time: float):
        """Print performance test results."""
        print(f"\n{Fore.CYAN}{'='*80}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Performance Test Results{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}\n")

        print(f"{Fore.GREEN}Test Duration:{Style.RESET_ALL} {elapsed_time:.2f} seconds")
        print(f"{Fore.GREEN}Total Requests:{Style.RESET_ALL} {self.total_requests}")
        print(f"{Fore.GREEN}Throughput:{Style.RESET_ALL} {self.total_requests / elapsed_time:.2f} req/s")
        print(f"{Fore.YELLOW}Rate Limit Hits:{Style.RESET_ALL} {self.rate_limit_hits}")

        if self.errors:
            print(f"\n{Fore.RED}Errors:{Style.RESET_ALL}")
            for error_type, count in self.errors.items():
                print(f"  {error_type}: {count}")

        print(f"\n{Fore.CYAN}Response Time Statistics (seconds){Style.RESET_ALL}")
        print(f"{'='*80}")
        print(f"{'Endpoint':<20} {'Count':<10} {'Min':<10} {'Max':<10} {'Mean':<10} {'P95':<10} {'P99':<10}")
        print(f"{'='*80}")

        for endpoint, times in sorted(self.results.items()):
            if times:
                count = len(times)
                min_time = min(times)
                max_time = max(times)
                mean_time = statistics.mean(times)
                # Use inclusive method to avoid P95/P99 exceeding max on small samples
                p95 = (
                    min(statistics.quantiles(times, n=20, method="inclusive")[18], max_time)
                    if len(times) > 1
                    else mean_time
                )
                p99 = (
                    min(statistics.quantiles(times, n=100, method="inclusive")[98], max_time)
                    if len(times) > 1
                    else mean_time
                )

                print(
                    f"{endpoint:<20} {count:<10} {min_time:<10.3f} {max_time:<10.3f} "
                    f"{mean_time:<10.3f} {p95:<10.3f} {p99:<10.3f}"
                )

        print(f"{'='*80}")

        # Performance assessment
        print(f"\n{Fore.CYAN}Performance Assessment{Style.RESET_ALL}")
        print(f"{'='*80}")

        # Check agent run performance
        if "agent_run" in self.results and self.results["agent_run"]:
            mean_agent = statistics.mean(self.results["agent_run"])
            if mean_agent < 2.0:
                status = f"{Fore.GREEN}Excellent{Style.RESET_ALL}"
            elif mean_agent < 5.0:
                status = f"{Fore.GREEN}Good{Style.RESET_ALL}"
            elif mean_agent < 10.0:
                status = f"{Fore.YELLOW}Acceptable{Style.RESET_ALL}"
            else:
                status = f"{Fore.RED}Needs Optimization{Style.RESET_ALL}"
            print(f"Agent Run Performance: {status} (mean: {mean_agent:.2f}s)")

        # Check get_runs performance
        if "get_runs" in self.results and self.results["get_runs"]:
            mean_get = statistics.mean(self.results["get_runs"])
            if mean_get < 0.1:
                status = f"{Fore.GREEN}Excellent{Style.RESET_ALL}"
            elif mean_get < 0.5:
                status = f"{Fore.GREEN}Good{Style.RESET_ALL}"
            else:
                status = f"{Fore.YELLOW}Could be improved{Style.RESET_ALL}"
            print(f"Get Runs Performance:  {status} (mean: {mean_get:.3f}s)")

        # Check health check performance
        if "health_check" in self.results and self.results["health_check"]:
            mean_health = statistics.mean(self.results["health_check"])
            if mean_health < 0.05:
                status = f"{Fore.GREEN}Excellent{Style.RESET_ALL}"
            elif mean_health < 0.2:
                status = f"{Fore.GREEN}Good{Style.RESET_ALL}"
            else:
                status = f"{Fore.YELLOW}Could be improved{Style.RESET_ALL}"
            print(f"Health Check Performance: {status} (mean: {mean_health:.3f}s)")

        # Rate limiting assessment
        if self.rate_limit_hits > 0:
            rate_limit_pct = (self.rate_limit_hits / self.total_requests) * 100
            print(f"\nRate Limiting: {Fore.YELLOW}Active{Style.RESET_ALL} ({rate_limit_pct:.1f}% requests limited)")
        else:
            print(f"\nRate Limiting: {Fore.GREEN}Not triggered{Style.RESET_ALL} at this load level")

        print(f"{'='*80}\n")

    async def test_rate_limiting(self):
        """Test rate limiting specifically with burst requests."""
        print(f"\n{Fore.CYAN}{'='*80}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Rate Limiting Test{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}\n")

        async with httpx.AsyncClient() as client:
            if not await self.authenticate(client):
                print(f"{Fore.RED}✗ Failed to authenticate{Style.RESET_ALL}")
                return

            print(f"Sending 100 rapid requests to test rate limits...")
            rate_limited = 0
            successful = 0
            errors = 0

            tasks = []
            for i in range(100):
                task = self.test_agent_run(client, i + 90000)
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, dict):
                    if result["status"] == "rate_limited":
                        rate_limited += 1
                    elif result["status"] == "success":
                        successful += 1
                    else:
                        errors += 1

            print(f"\n{Fore.GREEN}Successful:{Style.RESET_ALL} {successful}")
            print(f"{Fore.YELLOW}Rate Limited:{Style.RESET_ALL} {rate_limited}")
            print(f"{Fore.RED}Errors:{Style.RESET_ALL} {errors}")

            if rate_limited > 0:
                print(f"\n{Fore.GREEN}✓ Rate limiting is working correctly{Style.RESET_ALL}")
            else:
                print(
                    f"\n{Fore.YELLOW}⚠ Rate limiting not triggered - may need adjustment or is disabled{Style.RESET_ALL}"
                )

        print(f"{'='*80}\n")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Performance testing for agent endpoints")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of the API (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="Number of concurrent workers (default: 10)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Test duration in seconds (default: 30)",
    )
    parser.add_argument(
        "--email",
        default="admin@example.com",
        help="Login email (default: admin@example.com)",
    )
    parser.add_argument(
        "--password",
        default="changethisnowplease",
        help="Login password (default: changethisnowplease)",
    )
    parser.add_argument(
        "--rate-limit-only",
        action="store_true",
        help="Only test rate limiting (skip load test)",
    )

    args = parser.parse_args()

    tester = PerformanceTest(
        base_url=args.base_url,
        concurrency=args.concurrency,
        duration=args.duration,
        email=args.email,
        password=args.password,
    )

    try:
        if args.rate_limit_only:
            await tester.test_rate_limiting()
        else:
            await tester.run_load_test()
            await tester.test_rate_limiting()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Test interrupted by user{Style.RESET_ALL}")
    except Exception as e:
        print(f"\n{Fore.RED}Error during testing: {e}{Style.RESET_ALL}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
