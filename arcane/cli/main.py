"""Root Click group for the `arc` CLI."""

import click

from arcane.cli.cmd_init import init
from arcane.cli.cmd_add import add
from arcane.cli.cmd_rm import rm
from arcane.cli.cmd_status import status
from arcane.cli.cmd_commit import commit
from arcane.cli.cmd_log import log
from arcane.cli.cmd_diff import diff
from arcane.cli.cmd_branch import branch
from arcane.cli.cmd_checkout import checkout
from arcane.cli.cmd_merge import merge
from arcane.cli.cmd_tag import tag
from arcane.cli.cmd_impact import impact
from arcane.cli.cmd_annotate import annotate
from arcane.cli.cmd_debt_score import debt_score
from arcane.cli.cmd_graph import graph
from arcane.cli.cmd_cat import cat


@click.group()
@click.version_option(package_name="arcane")
def cli() -> None:
    """arcane — a version control system with intent, dependencies, and annotations."""


cli.add_command(init)
cli.add_command(add)
cli.add_command(rm)
cli.add_command(status)
cli.add_command(commit)
cli.add_command(log)
cli.add_command(diff)
cli.add_command(branch)
cli.add_command(checkout)
cli.add_command(merge)
cli.add_command(tag)
cli.add_command(impact)
cli.add_command(annotate)
cli.add_command(debt_score)
cli.add_command(graph)
cli.add_command(cat)
