# Linux syscalls worth knowing as an Elixir/Phoenix dev

BEAM hides a lot of OS detail, which is mostly a feature. But when production breaks, when you shell out to a program, when a container behaves oddly, or when you want to know *why* Phoenix scales the way it does — the answers live below BEAM, in the kernel.

This is a tour of the syscalls and concepts that pay off most. Treat it as a map, not a textbook.

## The mental model

Every running program is an **OS process** — a kernel-managed object with its own PID, memory space, and a per-process **file descriptor table**. An fd is just an integer that indexes into that table; the kernel keeps the real "open file" / "open socket" / "pipe" object behind it.

A BEAM VM is *one* OS process. Inside it, millions of Erlang processes share that one fd table, that one memory space, and that one set of OS-level resources. When you write `IO.puts/1`, the bytes ultimately leave BEAM through a `write(2)` syscall on one of BEAM's fds. The kernel doesn't know or care that Erlang exists.

That gap — between Erlang processes and OS processes — is where most of the interesting bugs live.

## Process lifecycle: `fork`, `exec`, `wait`, signals

- **`fork(2)`** clones the calling process. Child inherits memory (copy-on-write), open fds, working dir, env. Returns 0 in the child, child's PID in the parent.
- **`execve(2)`** replaces the current process image with a new program. Same PID, same fd table (mostly), new code.
- **`wait(2)` / `waitpid(2)`** reaps a finished child. Until reaped, the child is a *zombie* taking a slot in the kernel's process table.
- **Signals**: `SIGTERM` (polite stop), `SIGKILL` (uncatchable), `SIGINT` (Ctrl-C), `SIGCHLD` (a child finished), `SIGPIPE` (you wrote to a closed pipe).

Why an Elixir dev should care:
- **`System.cmd/3`, `Port`, `:erlexec`** all do fork+exec under the hood. If you don't drain the port or close it, you can leak zombies and fds.
- **PID 1 in Docker** has special semantics — it doesn't reap children automatically and ignores most signals by default. That's why containerized BEAM apps sometimes don't shut down cleanly on `docker stop` (which sends `SIGTERM`, waits, then `SIGKILL`). Use `tini` or set `init: true` in your compose file.
- **Graceful shutdown** in Phoenix releases: `SIGTERM` triggers BEAM's shutdown sequence, which runs your `Application.stop/1` callbacks. If you never receive `SIGTERM` (PID 1 problem), you skip straight to `SIGKILL` and drop in-flight requests.

## Pipes and fds

- **`pipe(2)`** creates an in-kernel FIFO buffer. Returns two fds: one for reading, one for writing. Anonymous, unidirectional.
- **`dup2(2)`** copies one fd onto another fd number. The classic trick for hooking up child stdio: `dup2(pipe_write_end, 1)` makes the child's stdout point at the pipe.
- **`close(2)`** drops the fd. When all fds pointing at a pipe end are closed, the other end gets EOF on read or `SIGPIPE` / `EPIPE` on write.

This is exactly what happens when a test runner spawns your program: parent calls `pipe()`, `fork()`s, the child `dup2()`s the write-end onto fd 1 and `execve()`s your binary. Your `IO.puts` writes bytes; the parent `read(2)`s from the read-end. The kernel pipe is the only bridge.

Why this matters in Phoenix-land:
- **`EMFILE` errors** ("too many open files") happen when you leak fds — usually unclosed `:gen_tcp` sockets, `File.open` handles, or `Port`s. `ulimit -n` controls the cap; raise it in production.
- **`:erlang.open_port/2`** with `{:spawn_executable, ...}` opens a pipe to a child. Forgetting to close the port leaks both the pipe fds and the child process.
- **`lsof -p <beam_pid>`** is your friend for hunting fd leaks. On Linux, `ls -l /proc/<pid>/fd/` shows the same info.

## Sockets — the part Phoenix actually leans on

- **`socket(2)`** creates a socket fd.
- **`bind(2)`** attaches it to an address/port.
- **`listen(2)`** turns it into a passive socket with a backlog queue.
- **`accept(2)`** pulls a connection off the backlog, returning a new fd for that conversation.
- **`read(2)` / `write(2)`** (or `recv`/`send`) move bytes.
- **`setsockopt(2)`** is where `SO_REUSEADDR`, `TCP_NODELAY`, `SO_KEEPALIVE` etc. live.

The thing that makes BEAM (and Phoenix) fast at high connection counts isn't magic — it's that BEAM uses **non-blocking IO** + **`epoll`** (Linux) or **`kqueue`** (BSD/macOS) under the hood. One OS thread can watch tens of thousands of socket fds and only wake up when there's data. BEAM's IO poller does exactly this. Cowboy/Bandit/Ranch ride on top of `:gen_tcp` which rides on top of `epoll`.

Why this matters:
- The C10K-style scaling Phoenix is famous for is mostly *kernel features* + BEAM scheduling. Understanding `epoll` demystifies "how does Phoenix handle 2M connections."
- **Backlog tuning**: the `listen(backlog)` value caps how many half-open connections wait. If your acceptor pool can't keep up, new connections get refused. Tunable via `:gen_tcp.listen/2` options.
- **TIME_WAIT, half-open sockets, `SO_REUSEPORT`**: when you redeploy and hit "address already in use," this is why.

## Tracing — how to actually learn this

Don't read syscall references in the abstract. Pick a curious moment and trace it.

- **Linux**: `strace -f -p <pid>` attaches to a running process (and its threads); `-e trace=network` filters; `-c` gives a summary table.
- **macOS**: `sudo dtruss -f -p <pid>` is the rough equivalent. Less polished than `strace`.
- **`lsof -p <pid>`** shows all open fds: files, pipes, sockets.
- **`ss -tnp`** (Linux) / `netstat -an` shows network sockets in detail.
- **`/proc/<pid>/`** on Linux has everything: `fd/`, `status`, `limits`, `maps`, `net/`.

Run a Phoenix server, hit it with `curl`, watch the syscalls. You'll see `accept`, `read`, `write`, `epoll_wait` — the whole loop. It clicks fast when you see it live.

## What's *not* worth deep-diving (for a Phoenix dev)

- Memory mapping (`mmap`) and virtual memory internals — interesting, but BEAM manages its own heap and you rarely touch this.
- `ptrace`, debugger internals.
- Assembly, ELF format, dynamic linker details.
- The full set of capabilities, namespaces, cgroups — *unless* you're writing your own container runtime.

These are great if you love systems work for its own sake. They're not force multipliers for shipping Phoenix apps.

## References

- **Kerrisk, *The Linux Programming Interface*** — the modern bible. Use as a reference, not a read-through.
- **Stevens, *Advanced Programming in the Unix Environment*** — older but still the clearest writing on this material.
- **`man 2 <syscall>`** — always current, always authoritative.
- **Julia Evans' zines** (jvns.ca) — excellent, friendly intros to `strace`, networking, containers.
- **BEAM book** (happi.github.io/theBeamBook) — for how Erlang itself maps to all of this.
