"""Command line entry points: `jarvis serve`, `jarvis chat`, `jarvis policy`."""

from __future__ import annotations

import argparse
import asyncio
import sys

from jarvis.config import load_settings


def _cmd_serve(_: argparse.Namespace) -> None:
    from jarvis.server.app import run

    run()


def _cmd_chat(args: argparse.Namespace) -> None:
    from jarvis.server.app import JarvisRuntime, MessageIn

    settings = load_settings()
    rt = JarvisRuntime(settings)

    async def printer(ev: dict) -> None:
        t = ev["type"]
        if t == "speak":
            print(f"\033[96m{settings.assistant_name}:\033[0m {ev['text']}")
        elif t == "tool_call" and ev.get("status") not in ("pending",):
            print(f"  \033[90m[tool {ev['name']} → {ev.get('status')}] {ev.get('input', '')}\033[0m")
        elif t == "tool_result":
            print(f"  \033[90m[result] {ev['result'][:200]}\033[0m")
        elif t == "approval_requested":
            print(f"  \033[93m[approval {ev['id']}] answer yes/no\033[0m")
        elif t == "turn_finished":
            print(f"  \033[90m[{ev.get('model')} {ev.get('tier')} ttft={ev.get('ttft_ms')}ms total={ev.get('total_ms')}ms "
                  f"in={ev.get('input_tokens')} out={ev.get('output_tokens')} cache_read={ev.get('cache_read_tokens')}]\033[0m")
        elif t == "error":
            print(f"  \033[91m[error] {ev['text']}\033[0m")
        elif t == "timer_fired":
            print(f"\033[95m⏰ {ev['speak']}\033[0m")

    async def main() -> None:
        rt.bus.subscribe(printer)
        await rt.start()
        print(f"{settings.assistant_name} ready. User: {args.user} ({rt.resolve_user(args.user).role}), room: {args.room}. Ctrl-D to quit.")
        loop = asyncio.get_event_loop()
        while True:
            try:
                line = await loop.run_in_executor(None, lambda: input("\033[92myou:\033[0m "))
            except EOFError:
                break
            if not line.strip():
                continue
            fut: asyncio.Future = loop.create_future()
            await rt._queue.put((MessageIn(text=line, user_id=args.user, room=args.room), fut))
            await fut
        await rt.stop()

    asyncio.run(main())


def _cmd_policy(_: argparse.Namespace) -> None:
    from jarvis.policy.permissions import PermissionEngine, User

    engine = PermissionEngine()
    tools = ["get_current_time", "remember", "forget_memory", "set_timer", "ha_call_service", "send_message", "unknown_tool"]
    samples = {"ha_call_service": {"domain": "lock", "service": "unlock", "entity_id": "lock.front_door"}}
    print(f"{'tool':<20}" + "".join(f"{r:<10}" for r in ("guest", "child", "adult", "owner")))
    for t in tools:
        row = f"{t:<20}"
        for role in ("guest", "child", "adult", "owner"):
            d, _r = engine.decide(t, samples.get(t, {}), User(id=role, name=role, role=role))
            row += f"{d.value:<10}"
        print(row)
    print("(ha_call_service row shown for lock.unlock; lights/media are allow for child and above)")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="jarvis", description="Jarvis personal AI assistant")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("serve", help="run the API server and dashboard").set_defaults(fn=_cmd_serve)
    c = sub.add_parser("chat", help="terminal conversation (no browser)")
    c.add_argument("--user", default="owner")
    c.add_argument("--room", default="office")
    c.set_defaults(fn=_cmd_chat)
    sub.add_parser("policy", help="print the permission table").set_defaults(fn=_cmd_policy)
    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main(sys.argv[1:])
