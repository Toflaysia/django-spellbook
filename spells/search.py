"""Unicode-aware substring search for SQLite, shared by pages, API and admin."""

from django.db.backends.signals import connection_created
from django.db.models import CharField, TextField
from django.db.models.lookups import IContains, Lookup


def casefold_text(value):
    return None if value is None else str(value).casefold()


def install_sqlite_casefold(sender, connection, **kwargs):
    if connection.vendor == "sqlite":
        connection.connection.create_function(
            "spellbook_casefold", 1, casefold_text, deterministic=True,
        )


class UnicodeIContains(IContains):
    # Keep standard Django SQL on other databases.
    def as_sqlite(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        # instr searches a literal substring, so do not add LIKE wildcards or escapes.
        rhs, rhs_params = Lookup.process_rhs(self, compiler, connection)
        return (
            f"INSTR(spellbook_casefold({lhs}), spellbook_casefold({rhs})) > 0",
            [*lhs_params, *rhs_params],
        )


def register_unicode_search():
    CharField.register_lookup(UnicodeIContains)
    TextField.register_lookup(UnicodeIContains)
    connection_created.connect(
        install_sqlite_casefold,
        dispatch_uid="spells.sqlite_unicode_search",
    )
