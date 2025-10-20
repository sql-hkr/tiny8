Tiny8 documentation
=====================

.. image:: https://img.shields.io/pypi/v/tiny8
   :target: <https://img.shields.io/pypi/v/tiny8>

.. image:: https://img.shields.io/github/license/sql-hkr/tiny8
   :target: <https://img.shields.io/github/license/sql-hkr/tiny8>

.. image:: https://img.shields.io/pypi/pyversions/tiny8
   :target: <https://img.shields.io/pypi/pyversions/tiny8>

.. image:: https://img.shields.io/github/actions/workflow/status/sql-hkr/tiny8/ci.yml?label=CI
   :target: <https://img.shields.io/github/actions/workflow/status/sql-hkr/tiny8/ci.yml?label=CI>

Tiny8 is a minimal, easy-to-use library for working with compact data structures and simple in-memory storage patterns.
It is designed for learning, experimentation, and small-scale projects where a lightweight dependency footprint is desirable.
This documentation covers installation, examples, and the API to help you get started quickly.

.. image:: _static/examples/bubblesort.gif
   :alt: Bubble sort

Installation
------------

Tiny8 supports Python 3.11 and newer. It has no heavy external dependencies and is suitable for inclusion in virtual environments.
Follow the steps below to prepare your environment and install from source or PyPI.

Prerequisites

- Python 3.11+
- Git (for installing from the repository)
- Recommended: create and use a virtual environment

From source (development)

.. code-block:: bash

   git clone https://github.com/sql-hkr/tiny8.git
   cd tiny8
   uv venv
   source .venv/bin/activate
   uv sync

.. tip::

   `uv <https://docs.astral.sh/uv/>`_ is an extremely fast Python package and project manager, written in Rust. To install it, run:

   .. code-block:: bash

      # On macOS and Linux.
      curl -LsSf https://astral.sh/uv/install.sh | sh

      # On Windows.
      powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

This flow sets up a development virtual environment, installs development requirements, and prepares the project for local editing and testing.

From PyPI (stable)

.. code-block:: bash

   uv add tiny8


Examples
--------

.. toctree::
   :maxdepth: 2

   examples/index

API Reference
---------------

The API section documents the public modules, classes, functions, and configuration options.
It includes usage notes, parameter descriptions, and return value details so you can use the library reliably in production code.

.. toctree::
   :maxdepth: 2

   api/tiny8

License
-------

Tiny8 is licensed under the MIT License. See `LICENSE <https://github.com/sql-hkr/tiny8/blob/main/LICENSE>`_ for details.
Contributions, bug reports, and pull requests are welcome; please follow the repository's CONTRIBUTING guidelines.
