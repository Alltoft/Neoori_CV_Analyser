"""Flask CLI commands (`flask <name>` inside the backend container)."""
import click


def register(app) -> None:
    @app.cli.command("purge-expired")
    @click.option("--dry-run", is_flag=True, help="Count only; delete nothing.")
    @click.option("--before-rollback", is_flag=True,
                  help="Every advisor row, unclaimed anonymous row and held draft, whatever its age.")
    @click.option("--apply", "apply_", is_flag=True,
                  help="With --before-rollback: delete (it only counts without it).")
    def purge_expired(dry_run, before_rollback, apply_):
        """Daily: delete the rows past their retention (four-doors spec, decision 46)."""
        from .services import purge

        apply = apply_ if before_rollback else not dry_run
        counts = purge.run(apply=apply, before_rollback=before_rollback)
        for kind, n in counts.items():
            click.echo(f"{kind}: {n}")
        click.echo("deleted" if apply else "dry run — nothing deleted")
