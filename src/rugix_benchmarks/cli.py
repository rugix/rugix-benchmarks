"""Command-line workflow for reproducible preparation, measurement and reporting."""
from __future__ import annotations

import logging
from pathlib import Path

import click

from . import bundles, fixtures, images, keys, runner, tools as toolchain
from .analysis import report as generate_report
from .common import CACHE, ROOT, load_plan, save_json
from .vm import build_native_image

@click.group()
def main():
    """Reproduce native delta-update measurements and their byte models."""
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")

@main.command("tools")
def build_tools():
    """Build pinned native tools and their complete guest dependency archive."""
    toolchain.prepare()
    keys.prepare()

@main.command("prepare")
@click.option("--plan",type=click.Path(exists=True,path_type=Path),multiple=True,
              default=("plans/paper.json","plans/calculator.json"))
@click.option("--import-corpus",type=click.Path(exists=True,path_type=Path))
def prepare(plan,import_corpus):
    """Build images, bundles, source indices and blank-target VM fixtures."""
    plans = [load_plan(path) for path in plan]
    workload_map = {}
    candidate_map = {}
    for item in plans:
        for workload in item.workloads:
            if workload.id in workload_map and workload_map[workload.id]!=workload:
                raise click.ClickException("Plans disagree on a workload")
            workload_map[workload.id] = workload
        for candidate in item.candidates:
            if candidate.id in candidate_map and candidate_map[candidate.id]!=candidate:
                raise click.ClickException("Plans disagree on a candidate")
            candidate_map[candidate.id] = candidate
    combined = plans[0].model_copy(update={"workloads":list(workload_map.values()),
                                         "candidates":list(candidate_map.values())})
    toolchain.prepare()
    keys.prepare()
    if import_corpus:
        images.import_cache(combined,import_corpus)
    images.prepare(combined)
    bundles.prepare(combined)
    bundles.simulate(combined)
    build_native_image()
    fixtures.prepare(combined)

@main.command("run")
@click.option("--plan",type=click.Path(exists=True,path_type=Path),default="plans/paper.json")
@click.option("--output",type=click.Path(path_type=Path),default=".cache/paper")
@click.option("--limit",type=click.IntRange(min=1))
def run(plan,output,limit):
    """Resume a campaign without replacing successful or failed evidence."""
    runner.run(load_plan(plan),plan,output.resolve(),limit=limit)

@main.command("smoke")
@click.option("--output",type=click.Path(path_type=Path),default=".cache/smoke")
def smoke(output):
    """Verify all native candidates once on the monthly pair at zero delay."""
    plan = load_plan(ROOT / "plans/paper.json")
    smoke_plan = plan.model_copy(update={"workloads":[plan.workloads[0]],"rtt_ms":[0],"repetitions":1})
    path = CACHE / "smoke-plan.json"
    save_json(path,smoke_plan)
    runner.run(smoke_plan,path,output.resolve())

@main.command("report")
@click.option("--paper",type=click.Path(exists=True,path_type=Path),default=".cache/paper")
@click.option("--calibration",type=click.Path(exists=True,path_type=Path),default=".cache/calculator")
def report(paper,calibration):
    """Validate complete campaigns and render tables, plots and correction data."""
    generate_report(paper.resolve(),calibration.resolve())

if __name__=="__main__":
    main()
