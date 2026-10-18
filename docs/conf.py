# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

# Add source directory to path for autodoc
sys.path.insert(0, os.path.abspath("../src"))

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "Tiny8"
copyright = "2025, sql-hkr"
author = "sql-hkr"
release = "0.2.0"
version = "0.2.0"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.todo",
    "sphinx.ext.mathjax",
    "sphinx.ext.githubpages",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

language = "en"
locale_dirs = ["locales/"]
gettext_compact = False

# -- Autodoc configuration ---------------------------------------------------
autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "special-members": "__init__",
    "undoc-members": True,
    "exclude-members": "__weakref__",
}

autodoc_typehints = "description"
autodoc_type_aliases = {}

# -- Napoleon settings -------------------------------------------------------
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = False
napoleon_use_admonition_for_notes = False
napoleon_use_admonition_for_references = False
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_preprocess_types = False
napoleon_type_aliases = None
napoleon_attr_annotations = True

# -- Intersphinx configuration -----------------------------------------------
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "matplotlib": ("https://matplotlib.org/stable/", None),
}

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "shibuya"
html_static_path = ["_static"]

# Theme options
html_theme_options = {
    "github_url": "https://github.com/sql-hkr/tiny8",
}

html_title = f"{project} {version} documentation"
html_short_title = project
html_favicon = None
html_logo = None

# -- Options for todo extension ----------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/extensions/todo.html#configuration

todo_include_todos = False  # Hide TODOs in production

# -- Options for LaTeX output ------------------------------------------------
latex_elements = {
    "papersize": "letterpaper",
    "pointsize": "10pt",
}

# -- Options for manual page output ------------------------------------------
man_pages = [("index", "tiny8", "Tiny8 Documentation", [author], 1)]

# -- Options for Texinfo output ----------------------------------------------
texinfo_documents = [
    (
        "index",
        "Tiny8",
        "Tiny8 Documentation",
        author,
        "Tiny8",
        "An educational 8-bit CPU simulator with interactive visualization",
        "Miscellaneous",
    ),
]


def setup(app):
    """Sphinx application setup hook."""

    def add_language_switcher_context(app, pagename, templatename, context, doctree):
        depth = pagename.count("/")
        prefix = "../" * depth
        outdir_name = os.path.basename(os.path.abspath(app.outdir))
        current_lang = app.config.language or "en"
        context["current_language"] = current_lang

        if outdir_name in ("en", "ja"):
            up_to_langs = prefix + "../"
            context["en_page_url"] = f"{up_to_langs}en/{pagename}.html"
            context["ja_page_url"] = f"{up_to_langs}ja/{pagename}.html"
        else:
            context["en_page_url"] = f"{prefix}en/{pagename}.html"
            context["ja_page_url"] = f"{prefix}ja/{pagename}.html"

    app.connect("html-page-context", add_language_switcher_context)
