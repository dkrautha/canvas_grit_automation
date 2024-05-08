# Build Systems

## Poetry

The primary use of Poetry is create the poetry.lock file, specifying what
dependencies are needed and their exact versions to use. It can also be used to
help with the development process if you do not have access to Nix, as a way to
create a virtual environment with all the dependencies installed. Check their
documentation for more information on how to use it to create a virtual
environment.

Poetry can be installed by following any of the instructions here:
<https://python-poetry.org/docs/#installing-with-pipx>. If you already have
Python and pip installed, then it should be fairly painless to install
[pipx](https://github.com/pypa/pipx) with pip and then Poetry with pipx.

A new dependency can be added with `poetry add PACKAGE`, where PACKAGE is the
name of the package you want to add. This will add it to the lock file, and
after a rebuild of nix it will be installed.

## Nix

Nix is the primary build system for the project. A special flake modules is
being use to read in the poetry.lock file, source the correct packages, and
build a development environment and source distribution. It is also capable of
building a docker image, which is the primary means for running the Sync
application.

The flake.nix file defines how the project itself is built, and you should
mostly not need to touch it at all.

The flake.lock file is similar to what poetry.lock is for, locking dependencies
to specific versions to ensure that build are reproducible. Do not edit this by
hand, you can update it with newer package versions if needed with
`nix flake update --commit-lock-file`. This will create a new commit with the
message being which flake inputs changed.
