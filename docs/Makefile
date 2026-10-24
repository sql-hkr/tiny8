# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line, and also
# from the environment for the first two.
SPHINXOPTS    ?=
SPHINXBUILD   ?= $(shell command -v sphinx-build 2>/dev/null || echo "uv run sphinx-build")
SOURCEDIR     = .
BUILDDIR      = _build

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile gettext update-po html html-ja html-en html-all apidoc

html: html-all

apidoc:
	@uv run sphinx-apidoc -f -o api ../src/tiny8 2>/dev/null || true

gettext: apidoc
	@$(SPHINXBUILD) -b gettext "$(SOURCEDIR)" locales/pot $(SPHINXOPTS)

update-po: gettext
	sphinx-intl update -p locales/pot -l ja -d locales

html-ja: apidoc
	@$(SPHINXBUILD) -b html -D language=ja "$(SOURCEDIR)" "$(BUILDDIR)/html/ja" $(SPHINXOPTS)

html-en: apidoc
	@$(SPHINXBUILD) -b html -D language=en "$(SOURCEDIR)" "$(BUILDDIR)/html/en" $(SPHINXOPTS)

html-all: html-en html-ja
	@mkdir -p "$(BUILDDIR)/html"
	@cp -f "$(SOURCEDIR)/_templates/root_index.html" "$(BUILDDIR)/html/index.html" 2>/dev/null || true

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
