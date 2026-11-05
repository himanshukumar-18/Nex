"""NEX Command Packages.

Exports all subcommands and functions for registration and testing.
"""

from nex.commands.config import app as config_app
from nex.commands.fix import app as fix_app
from nex.commands.fix import fix
from nex.commands.git import app as git_app
from nex.commands.init import app as init_app
from nex.commands.init import init
from nex.commands.inspect import app as inspect_app
from nex.commands.inspect import inspect
from nex.commands.pr import app as pr_app
from nex.commands.pr import pr
from nex.commands.repos import app as repos_app
from nex.commands.review import app as review_app
from nex.commands.review import review
from nex.commands.runs import app as runs_app
from nex.commands.security import app as security_app
from nex.commands.security import security
from nex.commands.test import app as test_app
from nex.commands.test import test

__all__ = [
    "config_app",
    "fix",
    "fix_app",
    "git_app",
    "init",
    "init_app",
    "inspect",
    "inspect_app",
    "pr",
    "pr_app",
    "repos_app",
    "review",
    "review_app",
    "runs_app",
    "security",
    "security_app",
    "test",
    "test_app",
]
