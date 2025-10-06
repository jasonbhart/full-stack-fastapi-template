#!/usr/bin/env python3
"""
Resource Monitoring Script for Performance Testing

Monitors CPU, memory, and container resource usage during performance tests.

Usage:
    python scripts/monitor_resources.py --duration 30 --interval 1
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime

from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)


class ResourceMonitor:
    """Monitor system and Docker container resources."""

    def __init__(self, duration: int = 30, interval: int = 1, output_file: str | None = None):
        self.duration = duration
        self.interval = interval
        self.output_file = output_file
        self.measurements = []

    def get_docker_stats(self) -> dict[str, dict]:
        """Get Docker container stats."""
        try:
            result = subprocess.run(
                ["docker", "stats", "--no-stream", "--format", "{{json .}}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                stats = {}
                for line in result.stdout.strip().split("\n"):
                    if line:
                        try:
                            data = json.loads(line)
                            container_name = data.get("Name", "unknown")
                            stats[container_name] = {
                                "cpu": data.get("CPUPerc", "0%").rstrip("%"),
                                "memory": data.get("MemUsage", "0B / 0B"),
                                "memory_pct": data.get("MemPerc", "0%").rstrip("%"),
                                "net_io": data.get("NetIO", "0B / 0B"),
                                "block_io": data.get("BlockIO", "0B / 0B"),
                            }
                        except json.JSONDecodeError:
                            continue
                return stats
            return {}
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return {}

    def parse_memory_usage(self, memory_str: str) -> tuple[float, float]:
        """Parse memory usage string like '123.4MiB / 1.5GiB' to MB values."""
        try:
            used_str, total_str = memory_str.split("/")
            used = self.convert_to_mb(used_str.strip())
            total = self.convert_to_mb(total_str.strip())
            return used, total
        except Exception:
            return 0.0, 0.0

    @staticmethod
    def convert_to_mb(size_str: str) -> float:
        """Convert size string to MB."""
        size_str = size_str.strip()
        if "GiB" in size_str or "GB" in size_str:
            return float(size_str.replace("GiB", "").replace("GB", "")) * 1024
        elif "MiB" in size_str or "MB" in size_str:
            return float(size_str.replace("MiB", "").replace("MB", ""))
        elif "KiB" in size_str or "KB" in size_str:
            return float(size_str.replace("KiB", "").replace("KB", "")) / 1024
        elif "B" in size_str:
            return float(size_str.replace("B", "")) / (1024 * 1024)
        return 0.0

    def monitor(self):
        """Monitor resources for the specified duration."""
        print(f"\n{Fore.CYAN}{'='*80}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Resource Monitoring{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}")
        print(f"Duration: {self.duration} seconds")
        print(f"Interval: {self.interval} second(s)")
        print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}\n")

        start_time = time.time()
        iteration = 0

        try:
            while time.time() - start_time < self.duration:
                timestamp = datetime.now().isoformat()
                stats = self.get_docker_stats()

                measurement = {
                    "timestamp": timestamp,
                    "elapsed": time.time() - start_time,
                    "containers": stats,
                }

                self.measurements.append(measurement)

                # Print current stats
                if iteration % 5 == 0:  # Print header every 5 iterations
                    print(f"\n{Fore.YELLOW}{'Timestamp':<20} {'Container':<30} {'CPU %':<10} {'Memory':<25}{Style.RESET_ALL}")
                    print("-" * 90)

                for container_name, container_stats in stats.items():
                    if "backend" in container_name.lower() or "redis" in container_name.lower():
                        cpu_val = float(container_stats["cpu"])
                        cpu_color = Fore.GREEN if cpu_val < 50 else Fore.YELLOW if cpu_val < 80 else Fore.RED

                        print(
                            f"{timestamp.split('T')[1][:8]:<20} {container_name:<30} "
                            f"{cpu_color}{container_stats['cpu']:>6}%{Style.RESET_ALL}  "
                            f"{container_stats['memory']:<25}"
                        )

                iteration += 1
                time.sleep(self.interval)

        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Monitoring interrupted{Style.RESET_ALL}")

        self.print_summary()

        if self.output_file:
            self.save_results()

    def print_summary(self):
        """Print monitoring summary."""
        print(f"\n{Fore.CYAN}{'='*80}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Resource Usage Summary{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}\n")

        # Aggregate stats by container
        container_stats = {}

        for measurement in self.measurements:
            for container, stats in measurement["containers"].items():
                if container not in container_stats:
                    container_stats[container] = {"cpu": [], "memory_used": [], "memory_total": []}

                try:
                    cpu_val = float(stats["cpu"])
                    container_stats[container]["cpu"].append(cpu_val)
                except (ValueError, KeyError):
                    pass

                try:
                    used, total = self.parse_memory_usage(stats["memory"])
                    if used > 0:
                        container_stats[container]["memory_used"].append(used)
                    if total > 0:
                        container_stats[container]["memory_total"].append(total)
                except (ValueError, KeyError):
                    pass

        # Print summary for each container
        for container in sorted(container_stats.keys()):
            if "backend" in container.lower() or "redis" in container.lower() or "db" in container.lower():
                stats = container_stats[container]
                print(f"{Fore.GREEN}{container}{Style.RESET_ALL}")

                if stats["cpu"]:
                    avg_cpu = sum(stats["cpu"]) / len(stats["cpu"])
                    max_cpu = max(stats["cpu"])
                    min_cpu = min(stats["cpu"])
                    print(f"  CPU:    Avg: {avg_cpu:>6.2f}%  Min: {min_cpu:>6.2f}%  Max: {max_cpu:>6.2f}%")

                # Initialize to avoid UnboundLocalError when memory_used is empty
                avg_mem = 0.0
                if stats["memory_used"]:
                    avg_mem = sum(stats["memory_used"]) / len(stats["memory_used"])
                    max_mem = max(stats["memory_used"])
                    min_mem = min(stats["memory_used"])
                    print(f"  Memory: Avg: {avg_mem:>6.0f}MB  Min: {min_mem:>6.0f}MB  Max: {max_mem:>6.0f}MB")

                if stats["memory_total"] and avg_mem > 0:
                    total_mem = stats["memory_total"][0]  # Should be constant
                    mem_pct = (avg_mem / total_mem) * 100
                    print(f"  Memory Usage: {mem_pct:.1f}% of {total_mem:.0f}MB")

                print()

        print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}\n")

    def save_results(self):
        """Save monitoring results to file."""
        try:
            with open(self.output_file, "w") as f:
                json.dump(
                    {"measurements": self.measurements, "summary": self.get_summary_dict()}, f, indent=2
                )
            print(f"{Fore.GREEN}✓ Results saved to {self.output_file}{Style.RESET_ALL}\n")
        except Exception as e:
            print(f"{Fore.RED}✗ Failed to save results: {e}{Style.RESET_ALL}\n")

    def get_summary_dict(self) -> dict:
        """Get summary as dictionary."""
        container_stats = {}

        for measurement in self.measurements:
            for container, stats in measurement["containers"].items():
                if container not in container_stats:
                    container_stats[container] = {"cpu": [], "memory_used": []}

                try:
                    container_stats[container]["cpu"].append(float(stats["cpu"]))
                except (ValueError, KeyError):
                    pass

                try:
                    used, _ = self.parse_memory_usage(stats["memory"])
                    if used > 0:
                        container_stats[container]["memory_used"].append(used)
                except (ValueError, KeyError):
                    pass

        summary = {}
        for container, stats in container_stats.items():
            summary[container] = {}
            if stats["cpu"]:
                summary[container]["cpu_avg"] = sum(stats["cpu"]) / len(stats["cpu"])
                summary[container]["cpu_max"] = max(stats["cpu"])
            if stats["memory_used"]:
                summary[container]["memory_avg_mb"] = sum(stats["memory_used"]) / len(stats["memory_used"])
                summary[container]["memory_max_mb"] = max(stats["memory_used"])

        return summary


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Monitor resource usage during performance tests")
    parser.add_argument(
        "--duration", type=int, default=30, help="Monitoring duration in seconds (default: 30)"
    )
    parser.add_argument(
        "--interval", type=int, default=1, help="Measurement interval in seconds (default: 1)"
    )
    parser.add_argument("--output", help="Output file for results (JSON format)")

    args = parser.parse_args()

    monitor = ResourceMonitor(duration=args.duration, interval=args.interval, output_file=args.output)

    try:
        monitor.monitor()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Monitoring interrupted{Style.RESET_ALL}")
        sys.exit(0)


if __name__ == "__main__":
    main()
