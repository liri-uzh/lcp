"""
Interface for interacting with lcpvian server

Not compiled to c!
"""

import asyncio
import sys

from .ddl_gen import main
from .dqd_parser import cmdline
from .cqp_to_json import cqp_to_json
from .project import refresh_config

COMMANDS = {
    "start",
    "lcpvian",
    "worker",
    "dqd",
    "cqp",
    "ddl",
    "config",
}

command = next((i for i in reversed(sys.argv) if i in COMMANDS), "lcpvian")

if command == "lcpvian" or command == "start":
    from .app import start

    print("Starting application...")
    start()

elif command == "config":
    asyncio.run(refresh_config())

elif command == "worker":
    from .worker import start_worker

    queue: str = next((i for i in reversed(sys.argv) if i not in COMMANDS), "internal")
    if queue not in ("internal", "query", "background"):
        queue = "internal"

    print("Starting worker...")
    start_worker(queue)

elif command == "dqd":
    print("Parsing DQD...")

    cmdline()

elif command == "cqp":
    print("Parsing CQP...")

    cqp_ar: list[str] = []
    for i in reversed(sys.argv):
        if i in COMMANDS:
            break
        cqp_ar = [i, *cqp_ar]

    print(cqp_to_json(" ".join(cqp_ar)))

elif command == "ddl":
    print("Creating DDL...")

    main(sys.argv[-1])

else:
    print(f"Command not understood: {command}")
