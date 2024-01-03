SPHINXOPTS	?=
SPHINXBUILD	?= sphinx-build
SPHINXAPIDOC	= sphinx-apidoc
SOURCEDIR	= docs/
BUILDDIR	= docs/_build
MODULE_PATH	= faster_sam

.PHONY: help
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

auto:
	@$(SPHINXAPIDOC) -feMT -o "$(SOURCEDIR)" "$(MODULE_PATH)"

%:
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
