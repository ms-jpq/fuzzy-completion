from asyncio import sleep
from json import JSONDecodeError, loads
from pathlib import Path
from typing import Iterator, Sequence

from pynvim.api.nvim import Nvim
from pynvim_pp.api import iter_rtps
from pynvim_pp.lib import awrite, go
from pynvim_pp.logging import log
from std2.asyncio import run_in_executor
from std2.pickle import DecodeError, new_decoder

from ...lang import LANG
from ...registry import atomic, rpc
from ...shared.timeit import timeit
from ...snippets.types import LoadedSnips
from ..rt_types import Stack

_DECODER = new_decoder(LoadedSnips)


async def _load(paths: Sequence[Path]) -> Sequence[LoadedSnips]:
    def cont() -> Iterator[LoadedSnips]:
        for path in paths:
            pre_compiled = path / "coq+snippets+v2.json"

            try:
                raw = pre_compiled.read_text("UTF-8")
            except FileNotFoundError:
                pass
            except OSError as e:
                log.warn("%s", f"{e} :: -- {pre_compiled}")
            else:
                try:
                    json = loads(raw)
                    loaded: LoadedSnips = _DECODER(json)
                except (JSONDecodeError, DecodeError) as e:
                    msg = f"failed to parse :: {e} -- {pre_compiled}"
                    log.warn("%s", msg)
                else:
                    yield loaded

    return await run_in_executor(lambda: tuple(cont()))


@rpc(blocking=True)
def compile_snips(nvim: Nvim, stack: Stack) -> None:
    paths = tuple(iter_rtps(nvim))

    async def cont() -> None:
        with timeit("LOAD SNIPS", force=True):
            loaded = await _load(paths)
            if not loaded:
                await sleep(0)
                await awrite(nvim, LANG("snip parse empty"))
            for l in loaded:
                await stack.sdb.populate(l)

    go(nvim, aw=cont())


atomic.exec_lua(f"{compile_snips.name}()", ())
