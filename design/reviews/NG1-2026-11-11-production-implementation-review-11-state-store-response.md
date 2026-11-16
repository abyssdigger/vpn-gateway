# Disposition — Production implementation review 11

F1 was accepted and fixed.

Runtime state now rejects symlinked parent directories, existing symlink targets
(including dangling symlinks), non-regular files, unexpected ownership and group/other
permissions. Atomic durable write semantics are retained.

No Draft 4 architecture change was required.
